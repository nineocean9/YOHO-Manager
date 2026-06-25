#!/usr/bin/env python3
"""Save sampling data for recreate_sample_3.0.py

Matches the exact data structure from interaction7_record_sample_3.0.py.
"""
import pickle, os, sys, argparse, math, random
import numpy as np
from pathlib import Path
import cv2

def sample(img, poi, rad, id, r_min, r_max, out_dir, iter_step=4):
    """Generate multi-scale patches (matching interaction7's sample() method)."""
    nms_dir = out_dir / 'nms'
    src_dir = out_dir / 'source'
    h, w = img.shape[:2]

    lst = list(range(r_max, r_min - 1, -iter_step))
    scale_r = max(math.ceil((r_max - rad) / iter_step), 2)
    if rad in lst:
        lst.remove(rad)
    lst.insert(0, rad)

    ind = {}
    cnd = {}

    for si, R in enumerate(lst):
        scale = si + 1
        sp = pow(math.ceil(rad / R), 2)
        ind[scale] = (R, sp)

        if R > rad:
            p_new = [(w // 2, h // 2)]
        else:
            area = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(area, poi, rad - R, 255, -1)
            idx = np.nonzero(area == 255)
            idx_list = list(zip(idx[1], idx[0]))
            if len(idx_list) < sp:
                sp = max(1, len(idx_list))
                p_new = idx_list[:sp]
            else:
                p_new = random.sample(idx_list, sp) if sp > 0 else [(poi[0], poi[1])]

        cnd[scale] = p_new

        for i, c in enumerate(p_new):
            # source mask (label)
            mask = np.zeros((h, w, 3), dtype=np.uint8)
            cv2.circle(mask, c, R, (255, 255, 255), -1)
            cv2.imwrite(str(src_dir / f'c-{id}-{scale}-{i+1}.png'), mask)

            # nms image patch (source)
            scope = img.copy()
            scope[mask[:,:,0] == 0] = 0
            cv2.imwrite(str(nms_dir / f'c-{id}-{scale}-{i+1}.png'), scope)

    return ind, cnd, scale_r

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--coords', required=True)  # "x1,y1,r1;x2,y2,r2"
    parser.add_argument('--img-w', type=int, default=480)
    parser.add_argument('--img-h', type=int, default=480)
    parser.add_argument('--img-path', default=None)
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent / 'EEC_save_sample_13.0'
    out_dir = base_dir / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'nms').mkdir(exist_ok=True)
    (out_dir / 'source').mkdir(exist_ok=True)

    points = []
    for part in args.coords.split(';'):
        if not part.strip(): continue
        x, y, r = map(int, part.strip().split(','))
        points.append((x, y, r))

    n_pts = len(points)
    if n_pts < 2:
        print('Need at least 2 sampling points')
        sys.exit(1)

    img = None
    if args.img_path and os.path.exists(args.img_path):
        img = cv2.imread(args.img_path)

    img_size = (args.img_h, args.img_w, 3)

    # Calculate r_min, r_max like interaction7 does
    r_min = int(max(args.img_h, args.img_w) / 256 * 8)
    if r_min % 2 != 0:
        r_min += 1
    r_max = 4 * r_min

    # Generate data for each sampling point
    cent = []
    ind = {}
    cnd = {}
    rnd = {}
    print(f'r_min={r_min}, r_max={r_max}')

    for i, (x, y, r) in enumerate(points):
        class_num = i + 1
        cent.append((x, y))
        print(f'Processing point {class_num}: ({x}, {y}, r={r})')

        if img is not None:
            c_ind, c_cnd, s_r = sample(img, (x, y), r, class_num, r_min, r_max, out_dir)
            nms_dir_str = str(out_dir / 'nms')
            print(f'  Got {len(c_ind)} scales, patches in nms: {len(os.listdir(nms_dir_str))}')
        else:
            # Minimal data structure without image
            rad = r
            lst = list(range(r_max, r_min - 1, -4))
            if rad in lst:
                lst.remove(rad)
            lst.insert(0, rad)
            c_ind = {}
            c_cnd = {}
            for si, R in enumerate(lst):
                c_ind[si+1] = (R, 1)
                c_cnd[si+1] = [(x, y)]
            s_r = max(math.ceil((r_max - rad) / 4), 2)

        ind[class_num] = c_ind
        cnd[class_num] = c_cnd
        rnd[class_num] = s_r

    # tind, tcnd same as ind, cnd
    tind = ind.copy()
    tcnd = cnd.copy()
    trnum = n_pts
    sp = img_size

    # Write PKL files
    for fname, data in [
        ('cent.pkl', cent), ('ind.pkl', ind), ('cnd.pkl', cnd),
        ('tcnd.pkl', tcnd), ('tind.pkl', tind), ('sp.pkl', sp),
        ('trnum.pkl', trnum), ('rnd.pkl', rnd)
    ]:
        p = out_dir / fname
        with open(p, 'wb') as f:
            pickle.dump(data, f)

    nms_files = [f for f in os.listdir(str(out_dir / 'nms')) if f.endswith('.png')]
    print(f'Generated {len(nms_files)} patches, 8 PKL files in {out_dir}')
    sys.exit(0)

if __name__ == '__main__':
    main()