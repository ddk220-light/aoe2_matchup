// Minimal ScreenCaptureKit recorder: captures the main display's VIDEO + SYSTEM AUDIO
// to a .mov, no loopback driver needed (uses the Screen Recording TCC grant).
// Usage: sck_record <out.mov> <seconds> [fps] [width] [height]
import Foundation
import ScreenCaptureKit
import AVFoundation
import CoreMedia
import CoreGraphics

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write("usage: sck_record <out.mov> <seconds> [fps] [width] [height]\n".data(using: .utf8)!)
    exit(2)
}
let outURL = URL(fileURLWithPath: args[1])
let seconds = Double(args[2]) ?? 10
let fps = args.count > 3 ? (Int(args[3]) ?? 60) : 60
let argW = args.count > 4 ? Int(args[4]) : nil
let argH = args.count > 5 ? Int(args[5]) : nil
try? FileManager.default.removeItem(at: outURL)

final class Recorder: NSObject, SCStreamOutput, SCStreamDelegate {
    let writer: AVAssetWriter
    let vInput: AVAssetWriterInput
    let aInput: AVAssetWriterInput
    var started = false

    init(width: Int, height: Int) throws {
        writer = try AVAssetWriter(outputURL: outURL, fileType: .mov)
        vInput = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: width,
            AVVideoHeightKey: height,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: 40_000_000,
                AVVideoMaxKeyFrameIntervalKey: fps * 2,
            ],
        ])
        vInput.expectsMediaDataInRealTime = true
        aInput = AVAssetWriterInput(mediaType: .audio, outputSettings: [
            AVFormatIDKey: kAudioFormatMPEG4AAC,
            AVSampleRateKey: 48000,
            AVNumberOfChannelsKey: 2,
            AVEncoderBitRateKey: 192_000,
        ])
        aInput.expectsMediaDataInRealTime = true
        writer.add(vInput)
        writer.add(aInput)
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer, of type: SCStreamOutputType) {
        guard CMSampleBufferDataIsReady(sb) else { return }
        switch type {
        case .screen:
            if let arr = CMSampleBufferGetSampleAttachmentsArray(sb, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]],
               let info = arr.first, let raw = info[.status] as? Int,
               let st = SCFrameStatus(rawValue: raw), st != .complete { return }
            if writer.status == .unknown {
                writer.startWriting()
                writer.startSession(atSourceTime: CMSampleBufferGetPresentationTimeStamp(sb))
                started = true
            }
            if started && vInput.isReadyForMoreMediaData { vInput.append(sb) }
        case .audio:
            if started && writer.status == .writing && aInput.isReadyForMoreMediaData { aInput.append(sb) }
        default: break
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        FileHandle.standardError.write("stream stopped: \(error)\n".data(using: .utf8)!)
    }

    func finish() {
        vInput.markAsFinished(); aInput.markAsFinished()
        let done = DispatchSemaphore(value: 0)
        writer.finishWriting { done.signal() }
        done.wait()
    }
}

var recorder: Recorder!
var theStream: SCStream!
var sigSrcs: [DispatchSourceSignal] = []
var stopping = false

// Stop capture and finalize the .mov (writes the moov atom). Safe to call from the
// deadline OR from a SIGINT/SIGTERM handler (graceful early stop). Idempotent.
func stopAndFinish() {
    if stopping { return }
    stopping = true
    guard theStream != nil else { exit(0) }
    theStream.stopCapture { _ in
        recorder.finish()
        FileHandle.standardError.write("done\n".data(using: .utf8)!)
        exit(0)
    }
}

SCShareableContent.getWithCompletionHandler { content, err in
    guard let content = content, let display = content.displays.first else {
        FileHandle.standardError.write("no display: \(String(describing: err))\n".data(using: .utf8)!)
        exit(1)
    }
    // native pixel size of the display
    let mode = CGDisplayCopyDisplayMode(display.displayID)
    let pxW = mode.map { $0.pixelWidth } ?? display.width
    let pxH = mode.map { $0.pixelHeight } ?? display.height
    let w = argW ?? pxW
    let h = argH ?? pxH

    let cfg = SCStreamConfiguration()
    cfg.width = w
    cfg.height = h
    cfg.minimumFrameInterval = CMTime(value: 1, timescale: CMTimeScale(fps))
    cfg.capturesAudio = true
    cfg.sampleRate = 48000
    cfg.channelCount = 2
    cfg.showsCursor = true
    cfg.pixelFormat = kCVPixelFormatType_32BGRA
    cfg.queueDepth = 8

    let filter = SCContentFilter(display: display, excludingWindows: [])
    do {
        recorder = try Recorder(width: w, height: h)
    } catch {
        FileHandle.standardError.write("writer init failed: \(error)\n".data(using: .utf8)!); exit(1)
    }
    theStream = SCStream(filter: filter, configuration: cfg, delegate: recorder)
    let q = DispatchQueue(label: "sck.out")
    do {
        try theStream.addStreamOutput(recorder, type: .screen, sampleHandlerQueue: q)
        try theStream.addStreamOutput(recorder, type: .audio, sampleHandlerQueue: q)
    } catch {
        FileHandle.standardError.write("addStreamOutput failed: \(error)\n".data(using: .utf8)!); exit(1)
    }
    theStream.startCapture { error in
        if let error = error {
            FileHandle.standardError.write("startCapture failed: \(error)\n".data(using: .utf8)!); exit(1)
        }
        FileHandle.standardError.write("recording \(w)x\(h)@\(fps) (cap \(seconds)s, stop early w/ SIGINT) -> \(outURL.path)\n".data(using: .utf8)!)
    }
    // safety cap: stop after `seconds` no matter what
    DispatchQueue.main.asyncAfter(deadline: .now() + seconds) { stopAndFinish() }
    // graceful early stop: SIGINT/SIGTERM -> finalize the file (not a hard kill, which
    // would leave the .mov unfinalized/corrupt). Used to stop when the game really ends.
    for sig in [SIGINT, SIGTERM] {
        signal(sig, SIG_IGN)
        let src = DispatchSource.makeSignalSource(signal: sig, queue: .main)
        src.setEventHandler { stopAndFinish() }
        src.resume()
        sigSrcs.append(src)
    }
}

dispatchMain()
