"""Alpha-aware sprite upscaler (Lanczos 4x + Real-ESRGAN 4x), halo-free.

Transparent pixels in the extracted PNGs carry RGB=(0,0,0); naive upscaling
bleeds that black into the silhouette (dark fringe) and, with ncnn-on-RGBA, can
hallucinate noisy semi-transparent backgrounds. This tool:
  1) edge-bleeds opaque RGB outward into transparent pixels (RGB only),
  2) upscales the now-opaque RGB (Lanczos and/or Real-ESRGAN x4plus),
  3) upscales the ORIGINAL alpha separately (Lanczos -> clean anti-aliased edge),
  4) recombines RGB + alpha.

Operates on every <slug>_<pose>.png "original" under graphics/extracted/<slug>/
(poses = files without a _lanczos4x / _esrgan4x suffix), writing/overwriting the
matching _lanczos4x.png and _esrgan4x.png. Real-ESRGAN uses the bundled
ncnn-vulkan build; folder-mode drops on some GPUs are repaired per-file.

Run:  python graphics/upscale_sprites.py [--scale 4] [--esrgan-exe <path>]
"""
import os, sys, glob, shutil, subprocess, argparse
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACT = os.path.join(ROOT, 'graphics', 'extracted')
DEFAULT_EXE = os.path.join(ROOT, '.scratch', 'tools', 're', 'realesrgan-ncnn-vulkan.exe')

def edge_bleed(rgba, iters=14):
    arr = np.array(rgba)
    rgb = arr[:, :, :3].astype(np.float32)
    filled = arr[:, :, 3] > 8
    for _ in range(iters):
        if filled.all():
            break
        ssum = np.zeros_like(rgb); cnt = np.zeros(filled.shape, np.float32)
        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            ssum += np.roll(np.roll(rgb, dy, 0), dx, 1) * \
                    np.roll(np.roll(filled, dy, 0), dx, 1).astype(np.float32)[:, :, None]
            cnt += np.roll(np.roll(filled, dy, 0), dx, 1).astype(np.float32)
        newly = (~filled) & (cnt > 0)
        rgb[newly] = ssum[newly] / cnt[newly, None]
        filled |= newly
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), 'RGB')

def is_blank_or_wrong(path, expect_size):
    try:
        im = Image.open(path)
        return im.size != expect_size or im.convert('L').getbbox() is None
    except Exception:
        return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scale', type=int, default=4)
    ap.add_argument('--esrgan-exe', default=DEFAULT_EXE)
    ap.add_argument('--model-pth', default=None,
                    help='Path to an ESRGAN .pth (e.g. 4x-UltraSharp); uses '
                         'spandrel+torch (run under a CUDA torch env) instead of '
                         'the bundled ncnn x4plus. Produces sharper sprite output.')
    a = ap.parse_args()
    S = a.scale
    EXE, WD = a.esrgan_exe, os.path.dirname(a.esrgan_exe)
    use_torch = bool(a.model_pth)
    have_esrgan = use_torch or os.path.exists(EXE)
    torch_model = None
    if use_torch:
        import torch
        from spandrel import ModelLoader
        torch_model = ModelLoader().load_from_file(a.model_pth).to('cuda').eval()

        def _torch_up(bled_pil):
            import numpy as _np
            arr = _np.asarray(bled_pil.convert('RGB')).astype('float32') / 255.0
            t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to('cuda')
            with torch.no_grad():
                o = torch_model(t)
            o = o.squeeze(0).clamp(0, 1).permute(1, 2, 0).cpu().numpy()
            return Image.fromarray((o * 255).round().astype('uint8'), 'RGB')
    BLED = os.path.join(ROOT, '.scratch', 'bled'); BUP = os.path.join(ROOT, '.scratch', 'bled_up')
    for d in (BLED, BUP):
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d)

    poses = []   # (slug, pose, native_path, alpha_image, bled_size)
    for nf in glob.glob(EXTRACT + '/*/*.png'):
        b = os.path.basename(nf)
        if '_lanczos' in b or '_esrgan' in b or b.startswith('_'):
            continue
        slug = os.path.basename(os.path.dirname(nf))
        pose = b[len(slug)+1:-4]
        rgba = Image.open(nf).convert('RGBA')
        bled = edge_bleed(rgba)
        flat = f'{slug}__{pose}.png'
        bled.save(os.path.join(BLED, flat))
        poses.append((slug, pose, rgba.split()[3], bled.size))
    print(f'prepared {len(poses)} bled images')

    # ESRGAN upscale of the bled (opaque) images -> BUP
    if use_torch:
        for slug, pose, _a, sz in poses:
            flat = f'{slug}__{pose}.png'
            _torch_up(Image.open(os.path.join(BLED, flat))).save(os.path.join(BUP, flat))
    elif have_esrgan:
        subprocess.run([EXE, '-i', BLED, '-o', BUP, '-n', 'realesrgan-x4plus', '-s', str(S)],
                       cwd=WD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for slug, pose, _a, sz in poses:
            flat = f'{slug}__{pose}.png'; outp = os.path.join(BUP, flat)
            for t in ('64', '32'):
                if not is_blank_or_wrong(outp, (sz[0]*S, sz[1]*S)):
                    break
                subprocess.run([EXE, '-i', os.path.join(BLED, flat), '-o', outp,
                                '-n', 'realesrgan-x4plus', '-s', str(S), '-t', t],
                               cwd=WD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # recombine + write
    n_l = n_e = 0
    for slug, pose, alpha, sz in poses:
        up_a = alpha.resize((sz[0]*S, sz[1]*S), Image.LANCZOS)
        bled = Image.open(os.path.join(BLED, f'{slug}__{pose}.png')).convert('RGB')
        udir = os.path.join(EXTRACT, slug)
        lz = bled.resize(up_a.size, Image.LANCZOS)
        Image.merge('RGBA', (*lz.split(), up_a)).save(
            os.path.join(udir, f'{slug}_{pose}_lanczos{S}x.png')); n_l += 1
        ep = os.path.join(BUP, f'{slug}__{pose}.png')
        if have_esrgan and not is_blank_or_wrong(ep, (sz[0]*S, sz[1]*S)):
            er = Image.open(ep).convert('RGB').resize(up_a.size)
            Image.merge('RGBA', (*er.split(), up_a)).save(
                os.path.join(udir, f'{slug}_{pose}_esrgan{S}x.png')); n_e += 1
    print(f'wrote lanczos={n_l} esrgan={n_e}')

if __name__ == '__main__':
    main()
