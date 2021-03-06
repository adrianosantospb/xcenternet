import math
import numpy as np


def gaussian_radius(det_size, min_overlap=0.7):
    height, width = det_size

    a1 = 1
    b1 = height + width
    c1 = width * height * (1 - min_overlap) / (1 + min_overlap)
    sq1 = np.sqrt(b1 ** 2 - 4 * a1 * c1)
    r1 = (b1 + sq1) / 2

    a2 = 4
    b2 = 2 * (height + width)
    c2 = (1 - min_overlap) * width * height
    sq2 = np.sqrt(b2 ** 2 - 4 * a2 * c2)
    r2 = (b2 + sq2) / 2

    a3 = 4 * min_overlap
    b3 = -2 * min_overlap * (height + width)
    c3 = (min_overlap - 1) * width * height
    sq3 = np.sqrt(b3 ** 2 - 4 * a3 * c3)
    r3 = (b3 + sq3) / 2
    return min(r1, r2, r3)


def gaussian2D(shape, sigma_x=1, sigma_y=1):
    m, n = [(ss - 1.0) / 2.0 for ss in shape]
    y, x = np.ogrid[-m : m + 1, -n : n + 1]

    # h = np.exp(-(x * x + y * y) / (2 * sigma * sigma))
    h = np.exp(-(x * x / (2 * sigma_x * sigma_x) + y * y / (2 * sigma_y * sigma_y)))
    h[h < np.finfo(h.dtype).eps * h.max()] = 0
    return h


def draw_umich_gaussian(heatmap, center, radius, k=1):
    diameter = 2 * radius + 1
    gaussian = gaussian2D((diameter, diameter), sigma_x=diameter / 6, sigma_y=diameter / 6)

    y, x = int(center[0]), int(center[1])

    height, width = heatmap.shape[0:2]

    left, right = min(x, radius), min(width - x, radius + 1)
    top, bottom = min(y, radius), min(height - y, radius + 1)

    masked_heatmap = heatmap[y - top : y + bottom, x - left : x + right]
    masked_gaussian = gaussian[radius - top : radius + bottom, radius - left : radius + right]
    if min(masked_gaussian.shape) > 0 and min(masked_heatmap.shape) > 0:  # TODO debug
        np.maximum(masked_heatmap, masked_gaussian * k, out=masked_heatmap)
    return heatmap


def draw_truncate_gaussian(heatmap, center, h_radius, w_radius, k=1):
    h, w = 2 * h_radius + 1, 2 * w_radius + 1
    sigma_x = w / 6
    sigma_y = h / 6
    gaussian = gaussian2D((h, w), sigma_x=sigma_x, sigma_y=sigma_y)

    y, x = int(center[0]), int(center[1])

    height, width = heatmap.shape[0:2]

    left, right = min(x, w_radius), min(width - x, w_radius + 1)
    top, bottom = min(y, h_radius), min(height - y, h_radius + 1)

    masked_heatmap = heatmap[y - top : y + bottom, x - left : x + right]
    masked_gaussian = gaussian[h_radius - top : h_radius + bottom, w_radius - left : w_radius + right]
    if min(masked_gaussian.shape) > 0 and min(masked_heatmap.shape) > 0:
        np.maximum(masked_heatmap, masked_gaussian * k, out=masked_heatmap)
    return heatmap


def draw_heatmap(shape, bboxes, labels):
    heat_map = np.zeros(shape, dtype=np.float32)
    for bbox, cls_id in zip(bboxes, labels):
        h, w = bbox[3] - bbox[1], bbox[2] - bbox[0]
        if h > 0 and w > 0:
            radius = gaussian_radius((math.ceil(h), math.ceil(w)))
            radius = max(0, int(radius))
            ct = np.array([(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2], dtype=np.float32)
            ct_int = ct.astype(np.int32)
            draw_umich_gaussian(heat_map[:, :, cls_id], ct_int, radius)

    return heat_map


def draw_heatmaps(shape, bboxes, labels):
    heat_map = np.zeros(shape, dtype=np.float32)
    for b in range(shape[0]):
        for bbox, cls_id in zip(bboxes[b], labels[b]):
            w, h = bbox[3] - bbox[1], bbox[2] - bbox[0]
            if h > 0 and w > 0:
                radius = gaussian_radius((math.ceil(h), math.ceil(w)))
                radius = max(0, int(radius))
                ct = np.array([(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2], dtype=np.float32)
                ct_int = ct.astype(np.int32)
                draw_umich_gaussian(heat_map[b, :, :, cls_id], ct_int, radius)

    return heat_map


def radius_ttf(bbox, h, w):
    alpha = 0.54
    h_radiuses_alpha = int(h / 2.0 * alpha)
    w_radiuses_alpha = int(w / 2.0 * alpha)
    return max(0, h_radiuses_alpha), max(0, w_radiuses_alpha)


import sys

np.set_printoptions(threshold=sys.maxsize)


def get_pred_wh(shape):
    h, w = shape
    base_step = 1
    shifts_x = np.arange(0, (w - 1) * base_step + 1, base_step, dtype=np.float32)
    shifts_y = np.arange(0, (h - 1) * base_step + 1, base_step, dtype=np.float32)
    shift_y, shift_x = np.meshgrid(shifts_y, shifts_x)
    base_loc = np.stack((shift_x, shift_y), axis=0)
    return base_loc


def draw_heatmaps_ttf(shape, bboxes, labels):
    heat_map = np.zeros(shape, dtype=np.float32)
    box_target = np.ones((shape[0], shape[1], shape[2], 4), dtype=np.float32)
    reg_weight = np.zeros((shape[0], shape[1], shape[2], 1), dtype=np.float32)
    box_target_offset = np.zeros((shape[0], shape[1], shape[2], 4), dtype=np.float32)

    meshgrid = get_pred_wh((shape[1], shape[2]))

    for b in range(shape[0]):
        # sort the boxes by the area from max to min
        areas = np.asarray([bbox_areas_log_np(np.asarray(bbox)) for bbox in bboxes[b]])
        indices = np.argsort(-areas)

        bboxes_new = bboxes[b][indices]
        labels_new = labels[b][indices]

        for bbox, cls_id in zip(bboxes_new, labels_new):
            bbox = np.asarray(bbox)
            area = bbox_areas_log_np(bbox)
            fake_heatmap = np.zeros((shape[1], shape[2]))
            w, h = bbox[3] - bbox[1], bbox[2] - bbox[0]

            if h > 0 and w > 0:
                # compute heat map
                h_radius, w_radius = radius_ttf(bbox, h, w)
                ct = np.array([(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2], dtype=np.float32)
                ct_int = ct.astype(np.int32)
                draw_truncate_gaussian(fake_heatmap, ct_int, h_radius, w_radius)
                heat_map[b, :, :, cls_id] = np.maximum(heat_map[b, :, :, cls_id], fake_heatmap)

                # computes indices where is the current heatmap
                box_target_inds = fake_heatmap > 0

                # compute bbox size for current heatmap of bbox
                box_target[b, box_target_inds, :] = bbox[:]

                # this is just for debug/test
                box_target_offset[b, box_target_inds, 0] = meshgrid[1, box_target_inds] - bbox[0]
                box_target_offset[b, box_target_inds, 1] = meshgrid[0, box_target_inds] - bbox[1]
                box_target_offset[b, box_target_inds, 2] = bbox[2] - meshgrid[1, box_target_inds]
                box_target_offset[b, box_target_inds, 3] = bbox[3] - meshgrid[0, box_target_inds]

                # compute weight map for current heatmap of bbox
                local_heatmap = fake_heatmap[box_target_inds]
                ct_div = local_heatmap.sum()
                local_heatmap *= area
                reg_weight[b, box_target_inds, 0] = local_heatmap / ct_div

                # print("box_target offset", box_target_offset[b, box_target_inds, :])
    # print("*****")
    return heat_map, box_target, reg_weight, box_target_offset


def bbox_areas_log_np(bbox):
    x_min, y_min, x_max, y_max = bbox[1], bbox[0], bbox[3], bbox[2]
    area = (y_max - y_min + 1) * (x_max - x_min + 1)
    return np.log(area)
