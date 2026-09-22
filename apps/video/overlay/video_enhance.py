"""Optional local super-resolution on gameplay only, before overlay composition."""
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F
from spandrel import ModelLoader


class LocalUpscaler:
    def __init__(self, weights, blend=.75):
        self.model = ModelLoader().load_from_state_dict(
            torch.load(weights, map_location='cpu', weights_only=True))
        self.model.cuda().eval()
        self.dtype = torch.float16 if self.model.supports_half else torch.float32
        self.model.to(dtype=self.dtype)
        self.blend = blend
        self.metadata = {'model': str(Path(weights).resolve()),
                         'architecture': self.model.architecture.id,
                         'nativeScale': self.model.scale, 'blend': blend,
                         'device': torch.cuda.get_device_name(),
                         'method': 'Per-frame local super-resolution, antialiased resize to viewport, blend with source',
                         'scope': 'Gameplay only; overlays are composed afterward',
                         'temporalModel': False}

    def __call__(self, bgr):
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        with torch.inference_mode():
            source = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(
                device='cuda', dtype=self.dtype) / 255
            enhanced = self.model(source)
            # Keep the delivery format and overlays at 1080x1920. The model
            # works at native 4x internally, then its detail is sampled down.
            enhanced = F.interpolate(enhanced.float(), size=bgr.shape[:2],
                                     mode='bicubic', align_corners=False, antialias=True)
            result = (enhanced*self.blend + source.float()*(1-self.blend)).clamp(0, 1)
            result = (result[0].permute(1, 2, 0)*255).round().byte().cpu().numpy()
        return np.ascontiguousarray(result[:, :, ::-1])
