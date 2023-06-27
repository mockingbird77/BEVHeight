import argparse
import os
import cv2

from scripts.data_converter.visual_utils import *

import warnings
warnings.filterwarnings("ignore")

def kitti_visual_tool(data_root, demo_dir):
    if not os.path.exists(data_root):
        raise ValueError("data_root Not Found")
    if not os.path.exists(demo_dir):
        os.makedirs(demo_dir)
    img_suffix = ".png"
    if "rope" in data_root:
        img_suffix = ".png"
    elif "dair" in data_root:
        img_suffix = ".jpg"
    image_path = os.path.join(data_root, "training/image_2")
    calib_path = os.path.join(data_root, "training/calib")
    label_path = os.path.join(data_root, "training/label_2")
    
    image_ids = []
    for image_file in os.listdir(image_path):
        image_ids.append(image_file.split(".")[0])
    for i in range(len(image_ids)):
        print(image_ids[i])
        image_2_file = os.path.join(image_path, str(image_ids[i]) + img_suffix) # or png 
        calib_file = os.path.join(calib_path, str(image_ids[i]) + ".txt")
        label_2_file = os.path.join(label_path, str(image_ids[i]) + ".txt")
        image = cv2.imread(image_2_file)
        _, P2, denorm = load_calib(calib_file)
        image = draw_3d_box_on_image(image, label_2_file, P2, denorm)
        cv2.imwrite(os.path.join(demo_dir, str(image_ids[i]) + ".jpg"), image)

def kitti_visual_tool_eval(data_root, demo_dir , eval_dir ):

    if not os.path.exists(data_root):
        raise ValueError("data_root Not Found")
    if not os.path.exists(eval_dir):
        raise ValueError("eval_dir Not Found")
    if not os.path.exists(demo_dir):
        os.makedirs(demo_dir)
    img_suffix = ".png"
    if "rope" in data_root:
        img_suffix = ".png"
    elif "dair" in data_root:
        img_suffix = ".jpg"
    image_path = os.path.join(data_root, "training/image_2")
    calib_path = os.path.join(data_root, "training/calib")
    label_path = os.path.join(data_root, "training/label_2")
    eval_label_path = os.path.join(eval_dir,"data")
    
    label_ids = []
    for label_file in os.listdir(eval_label_path):
        label_ids.append(label_file.split(".")[0])
    for i in range(len(label_ids)):
        print(label_ids[i])
        image_2_file = os.path.join(image_path, str(label_ids[i]) + img_suffix) # or png 
        calib_file = os.path.join(calib_path, str(label_ids[i]) + ".txt")
        label_2_file = os.path.join(label_path, str(label_ids[i]) + ".txt")
        eval_label_file = os.path.join(eval_label_path, str(label_ids[i]) + ".txt")
        image = cv2.imread(image_2_file)
        _, P2, denorm = load_calib(calib_file)
        gt_image = draw_3d_box_on_image(image, label_2_file, P2, denorm)
        # image = cv2.imread(image_2_file)
        eval_image = draw_3d_box_on_image(image, eval_label_file, P2, denorm, gt = False)
        cv2.imwrite(os.path.join(demo_dir, str(label_ids[i]) + "eval" + ".jpg"), eval_image)
        cv2.imwrite(os.path.join(demo_dir, str(label_ids[i]) + "gt" + ".jpg"), gt_image)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dataset in KITTI format Checking ...")
    parser.add_argument("--data_root", type=str,
                        default="",
                        help="Path to Dataset root in KITTI format")
    parser.add_argument("--demo_dir", type=str,
                        default="",
                        help="Path to demo directions")
    parser.add_argument("--eval_dir", type=str,
                    default="",
                    help="Path to eval directions")
    args = parser.parse_args()
    os.makedirs(args.demo_dir, exist_ok=True)
    if args.eval_dir == "":
        kitti_visual_tool(args.data_root, args.demo_dir)
    else:
        kitti_visual_tool_eval(args.data_root,args.demo_dir,args.eval_dir)