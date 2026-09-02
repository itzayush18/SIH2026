"""Train a U-Net oil/no-oil segmenter on the Zenodo Sentinel-1 dataset — the
"honest 0.85+ IoU number" upgrade over the simulated-scene logistic classifier
in sagar/data/oil_classifier.json.

    pip install torch segmentation-models-pytorch pillow

The Zenodo archives are .7z, not .zip:

    brew install p7zip            # or: apt install p7zip-full
    7z x data/zenodo/part1/01_Train_Val_Oil_Spill_images.7z -o data/zenodo/part1/images
    7z x data/zenodo/part1/01_Train_Val_Oil_Spill_mask.7z   -o data/zenodo/part1/masks

Nobody on this side has actually opened that archive yet, so the image/mask
directory layout and mask pixel encoding (binary vs a multi-class colour
palette) are unverified. Run --inspect FIRST — it pairs files, prints how many
pairs it found, and prints the unique pixel values in a few sample masks, so a
layout or encoding mismatch shows up before a multi-hour training run instead
of after:

    python scripts/train_unet.py \\
        --images 'data/zenodo/part1/images/**/*.jpg' \\
        --masks  'data/zenodo/part1/masks/**/*.jpg' \\
        --inspect

If --inspect shows more than 2 unique mask values, the dataset is multi-class
(sea/oil/look-alike/ship/land is a common palette for this kind of set) —
pass --mask-values with the integer(s) that mean "oil" once you know them,
e.g. --mask-values 255 or --mask-values 1,2 for the flattened classes.

Then train for real:

    python scripts/train_unet.py \\
        --images 'data/zenodo/part1/images/**/*.jpg' \\
        --masks  'data/zenodo/part1/masks/**/*.jpg' \\
        --epochs 20 --batch-size 8 --out data/models/unet_v1.pt
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time

import numpy as np


def find_pairs(images_glob, masks_glob):
    imgs = {os.path.splitext(os.path.basename(p))[0]: p
            for p in glob.glob(images_glob, recursive=True)}
    masks = {os.path.splitext(os.path.basename(p))[0]: p
             for p in glob.glob(masks_glob, recursive=True)}
    common = sorted(set(imgs) & set(masks))
    return [(imgs[k], masks[k]) for k in common], len(imgs), len(masks)


def inspect(images_glob, masks_glob, n_samples=5):
    from PIL import Image
    pairs, n_img, n_mask = find_pairs(images_glob, masks_glob)
    print(f"{n_img} image(s) matched by --images, {n_mask} by --masks, "
          f"{len(pairs)} paired by filename stem")
    if not pairs:
        sys.exit("no pairs found — check the globs (remember to quote them so "
                 "the shell doesn't expand **) and that images/masks share "
                 "filename stems")
    for img_path, mask_path in pairs[:n_samples]:
        im = np.array(Image.open(img_path))
        mk = np.array(Image.open(mask_path))
        uniq = np.unique(mk)
        uniq_show = uniq[:10].tolist() if len(uniq) <= 10 else f"{len(uniq)} distinct values"
        print(f"  {os.path.basename(img_path):40s} img {im.shape} {im.dtype}  "
              f"mask {mk.shape} {mk.dtype}  unique={uniq_show}")
    print("\nif unique mask values are close to {0, 255} (small in-between "
          "values are normal JPEG compression noise at mask edges, harmless "
          "under the default >127 threshold), the default binary mode "
          "(--mask-values unset) is correct. If instead you see several "
          "genuinely distinct classes (e.g. 0/1/2/3/4 for sea/oil/lookalike/"
          "ship/land), pass --mask-values with the id(s) meaning oil.")


def build_model(in_channels):
    try:
        import segmentation_models_pytorch as smp
    except ImportError:
        sys.exit("pip install segmentation-models-pytorch")
    return smp.Unet(encoder_name="resnet34", encoder_weights="imagenet",
                    in_channels=in_channels, classes=1, activation=None)


def load_array(path, channels):
    from PIL import Image
    arr = np.array(Image.open(path)).astype(np.float32)
    if arr.ndim == 2:
        arr = arr[..., None]
    if arr.shape[-1] >= channels:
        arr = arr[..., :channels]
    else:
        arr = np.repeat(arr[..., :1], channels, axis=-1)
    return arr


def load_and_resize_image(path, channels, size):
    """Resize each channel plane separately — PIL chokes on arbitrary-channel
    arrays (e.g. 2-band VV/VH) if you hand it the whole stack at once."""
    from PIL import Image
    arr = load_array(path, channels)
    planes = [np.array(Image.fromarray(arr[..., c].astype(np.uint8))
                       .resize((size, size), Image.BILINEAR))
              for c in range(channels)]
    return np.stack(planes, axis=-1).astype(np.float32) / 255.0


def make_dataset(pairs, size, channels, mask_values):
    import torch
    from torch.utils.data import Dataset

    class SlickDataset(Dataset):
        def __len__(self):
            return len(pairs)

        def __getitem__(self, i):
            from PIL import Image
            img_path, mask_path = pairs[i]
            x = load_and_resize_image(img_path, channels, size)

            mk = np.array(Image.open(mask_path).convert("L").resize(
                (size, size), Image.NEAREST))
            if mask_values:
                y = np.isin(mk, mask_values).astype(np.float32)
            else:
                y = (mk > 127).astype(np.float32)

            xt = torch.from_numpy(x.transpose(2, 0, 1)).float()
            yt = torch.from_numpy(y).float().unsqueeze(0)
            return xt, yt

    return SlickDataset()


def iou_score(pred, target, eps=1e-6):
    pred = (pred > 0.5).float()
    inter = (pred * target).sum()
    union = pred.sum() + target.sum() - inter
    return ((inter + eps) / (union + eps)).item()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="glob, quoted, e.g. 'data/.../*.jpg'")
    ap.add_argument("--masks", required=True)
    ap.add_argument("--inspect", action="store_true", help="pair + report, then exit")
    ap.add_argument("--mask-values", default=None,
                     help="comma-separated pixel value(s) meaning 'oil'; default: pixel > 127")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--channels", type=int, default=1)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--out", default="data/models/unet_v1.pt")
    ap.add_argument("--device", default=None, help="default: cuda if available, else cpu")
    a = ap.parse_args()

    if a.inspect:
        inspect(a.images, a.masks)
        return

    if a.size % 32 != 0:
        sys.exit(f"--size {a.size} must be a multiple of 32 (resnet34 encoder "
                 "downsamples 5x — a non-multiple breaks the skip connections)")

    mask_values = ([int(v) for v in a.mask_values.split(",")]
                   if a.mask_values else None)

    pairs, n_img, n_mask = find_pairs(a.images, a.masks)
    if not pairs:
        sys.exit(f"no pairs found ({n_img} images, {n_mask} masks matched the globs "
                 "separately) — run with --inspect first")
    print(f"{len(pairs)} paired image/mask files")

    import torch
    from torch.utils.data import DataLoader, random_split

    device = a.device or ("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cpu":
        print("WARNING: no CUDA device found — this will be slow. "
              "Check `nvidia-smi` / your torch install (cu12x wheel) before committing hours to this.")
    print(f"device: {device}")

    ds = make_dataset(pairs, a.size, a.channels, mask_values)
    n_val = max(1, int(len(ds) * a.val_frac))
    n_train = len(ds) - n_val
    train_ds, val_ds = random_split(ds, [n_train, n_val],
                                    generator=torch.Generator().manual_seed(0))
    train_dl = DataLoader(train_ds, batch_size=a.batch_size, shuffle=True, num_workers=4)
    val_dl = DataLoader(val_ds, batch_size=a.batch_size, shuffle=False, num_workers=2)
    print(f"train {n_train}  val {n_val}")

    model = build_model(a.channels).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    bce = torch.nn.BCEWithLogitsLoss()

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    best_iou = -1.0
    for epoch in range(a.epochs):
        t0 = time.time()
        model.train()
        train_loss = 0.0
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            logits = model(x)
            loss = bce(logits, y)
            loss.backward()
            opt.step()
            train_loss += loss.item() * x.size(0)
        train_loss /= n_train

        model.eval()
        ious = []
        with torch.no_grad():
            for x, y in val_dl:
                x, y = x.to(device), y.to(device)
                pred = torch.sigmoid(model(x))
                for i in range(x.size(0)):
                    ious.append(iou_score(pred[i], y[i]))
        val_iou = float(np.mean(ious)) if ious else 0.0
        dt = time.time() - t0
        print(f"epoch {epoch+1:3d}/{a.epochs}  loss {train_loss:.4f}  "
              f"val IoU {val_iou:.3f}  ({dt:.0f}s)")

        if val_iou > best_iou:
            best_iou = val_iou
            torch.save(dict(model=model.state_dict(), channels=a.channels,
                            size=a.size, val_iou=val_iou), a.out)
            print(f"  -> saved {a.out} (best val IoU so far)")

    print(f"\ndone. best val IoU {best_iou:.3f} -> {a.out}")
    print("this is a standalone checkpoint — wiring it in as sagar's "
          "DetectionModel (docs/OILTRACE.md sec 9) is a separate follow-up, "
          "not required for the training win itself.")


if __name__ == "__main__":
    main()
