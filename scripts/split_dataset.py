import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import random
from tqdm import tqdm
import json
import math
import shutil


def read_all_txt(folder_path):
    camera_dict = {} # camera - intri - extri
    camera_ground_dict = {}  # camera - intri - ground
    #camera_denorm_dict = {}
    image_dict = {}  # camera intri - image index 
    count_dict = {}
    camera_count = 0
    camera_denorm_count = 0
    i = 0 
    for file_name in tqdm(os.listdir(folder_path)):
        i = i +1
        if file_name.endswith('.txt'):
            file_path = os.path.join(folder_path,file_name)
            with open(file_path,'r') as f:
                lines =  f.readlines()
                camera_intri = lines[2].strip().split()  # camera P2 intri 
                camera_extri = lines[5].strip().split()  # velo to cam    
                if camera_intri[1] not in camera_dict:
                    camera_dict[camera_intri[1]] = camera_extri[1]
                    file_idx = file_name.split(".txt")
                    image_dict[camera_intri[1]] = [file_idx[0]]
                    count_dict[camera_intri[1]] = 0
                    camera_count = camera_count + 1
                else:
                    if camera_dict[camera_intri[1]] != camera_extri[1]:
                        print("one intri to one more extri!")
                        raise KeyError
                    file_idx = file_name.split(".txt")
                    image_dict[camera_intri[1]].append(file_idx[0])
                    count_dict[camera_intri[1]] = count_dict[camera_intri[1]] + 1
            denorm_path = os.path.join(os.path.dirname(folder_path),"denorm",file_name)
            with open(denorm_path,'r') as f:
                denorm_lines =  f.readlines()
                denorm = denorm_lines[0].strip().split()   # denorm is a 4 valus list                
                if camera_intri[1] not in camera_ground_dict:
                    intri_extri_denorm = [camera_intri[1:],camera_extri[1:],denorm]
                    camera_ground_dict[camera_intri[1]] = intri_extri_denorm
                    camera_denorm_count = camera_denorm_count + 1
                if  camera_denorm_count != camera_count:
                    print("intri extri count not equal to denorm count!")
                    raise KeyError

        # if i > 100:
        #     print("image_dict",image_dict)
        #     print("count_dict",count_dict)
        #     print("camera_dict",camera_dict)

    print("camera_count",camera_count)
    return camera_dict, image_dict, count_dict, camera_ground_dict


#  对数据集进行切分，可以确定比例和是否是
def split_data_rope(image_dict,count_dict,height_dict = None):
    all_count = 0
    for camera_intri,image_count in count_dict.items():
        all_count= all_count+image_count
    tmp_count = 0
    train_list = []
    test_list = []
    train_id_list = []
    test_id_list = []
    
    if height_dict is None:
        camera_ids = list(count_dict.keys())
        random.shuffle(camera_ids)

        for camera_id in camera_ids:
            tmp_count += count_dict[camera_id]
            if tmp_count/all_count <= 0.8:
                image_list = image_dict[camera_id]
                train_list.extend(image_list)
                train_id_list.append(camera_id)
            else:
                image_list = image_dict[camera_id]
                test_list.extend(image_list)
                test_id_list.append(camera_id)
    else: 
        sorted_height_dict = dict(sorted(height_dict.items(), key=lambda x: x[1]))
        print("sorted_height_dict", sorted_height_dict)

        sorted_camera_ids = list(sorted_height_dict.keys())
        print("sorted_camera_ids",sorted_camera_ids)

        for camera_id in sorted_camera_ids:
            tmp_count += count_dict[camera_id]
            if tmp_count/all_count <= 0.2:
                image_list = image_dict[camera_id]
                test_list.extend(image_list)
                test_id_list.append(camera_id)
            else:
                image_list = image_dict[camera_id]
                train_list.extend(image_list)
                train_id_list.append(camera_id)
    train_list.sort()
    print("train_list",train_list[::200])
    test_list.sort()
    print("test_list",test_list[::200])
    camera_id_split = {"train":train_id_list, "test": test_id_list}
    return train_list, test_list,camera_id_split

def read_json(json_path):
    with open(json_path, 'r') as f:
        rope_kittiid = json.load(f)

    kitti_rope = {v:k for k,v in rope_kittiid.items() }
    return kitti_rope

def write_split(root_path, map2id_path,train_list,test_list,generate_path, height_dict, split_camera_set):
    kitti_rope = read_json(map2id_path)
    os.makedirs(generate_path, exist_ok=True)
    dataset_txt_path = os.path.join(generate_path,"set_split_info.txt")
    train_txt_path = os.path.join(generate_path,"train.txt")
    test_txt_path = os.path.join(generate_path,"val.txt")
    with open(train_txt_path,"w") as f:
        for item in train_list:
            f.write("%s\n"% kitti_rope[item])
    with open(test_txt_path,"w") as f:
        for item in test_list:
            f.write("%s\n"% kitti_rope[item])
    with open(dataset_txt_path,"w") as f:
        f.write("train list count %s\n"%str(len(train_list)) )
        f.write("train list count occ %s\n"%str(len(train_list)/(len(test_list) + len(train_list))))        
        f.write("val list count %s\n"%str(len(test_list)) )
        f.write("val list count occ %s\n"%str(len(test_list)/(len(test_list) + len(train_list))))
        f.write("train height:  \n" )
        for item in split_camera_set["train"]:
            f.write("%s\n"% str(height_dict[item]))
        f.write("test height:   \n" )
        for item in split_camera_set["test"]:
            f.write("%s\n"% str(height_dict[item]))
    copyfile(generate_path,root_path)
    print("generated in ",generate_path)

def copyfile(generate_path,root_path):
    
    train_txt_path = os.path.join(generate_path,"train.txt")
    test_txt_path = os.path.join(generate_path,"val.txt")
    shutil.copy2(train_txt_path, os.path.join(root_path, "data/rope3d/training/train.txt"))
    shutil.copy2(test_txt_path, os.path.join(root_path, "data/rope3d/validation/val.txt"))

def get_all_intri_extri(camera_list,data_path,height_dict):
    os.makedirs(data_path, exist_ok=True)
    txt_path  = os.path.join(data_path,"camera_intri_extri.txt")
    with open(txt_path,"w") as f:
        for key, intri_extri_denorm in camera_list.items():
                print(intri_extri_denorm)
                f.write("intri:\t")
                for item in intri_extri_denorm[0]:
                    f.write("%s\t"%item)
                f.write("\n")

                f.write("extri:\t")
                for item in intri_extri_denorm[1]:
                    f.write("%s\t"%item)
                f.write("\n")

                f.write("denorm:\t")
                for item in intri_extri_denorm[2]:
                    f.write("%s\t"%item)
                f.write("\n")

                # height
                f.write("height:\t")
                f.write("%s\t"%height_dict[key])
                f.write("\n")

def get_float_list(string_list):
    float_list = []

    for string in string_list:
        try:
            float_number = float(string)
            float_list.append(float_number)
        except ValueError:
            print(f"can't  transfer '{string}' to float")

    return float_list


def get_camera_height(intri_extri_denorm_dict):
    height_dict = {}
    for key, intri_extri_denorm in intri_extri_denorm_dict.items():
        intri = get_float_list(intri_extri_denorm[0])
        extri = get_float_list(intri_extri_denorm[1])
        denorm =  get_float_list(intri_extri_denorm[2])
        height = distance_to_plane(denorm,extri[0],extri[1],extri[2])    
        if key in height_dict:
            print("error: repeat key exist")
        height_dict[key] = height

    return height_dict


def distance_to_plane(denorm,x0, y0, z0):
    A, B, C, D = denorm[0],denorm[1],denorm[2],denorm[3]
    # numerator = A*x0 + B*y0 + C*z0 + D
    numerator = D
    denominator = math.sqrt(A**2 + B**2 + C**2)
    distance = abs(numerator / denominator)
    return distance





# 1. each time，generate data split txt file in generate path.
# 2. copy this file into rope3d/training and rope3d/validation, generate info file by gen_info_rope3d.py

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="Dataset in KITTI format Checking ...")
    # parser.add_argument("--data_root", type=str,
    #                     default="",
    #                     help="Path to Dataset root in KITTI format")
    # parser.add_argument("--demo_dir", type=str,
    #                     default="",
    #                     help="Path to demo directions")
    # parser.add_argument("--eval_dir", type=str,
    #                 default="",
    #                 help="Path to eval directions")
    # args = parser.parse_args()
    # os.makedirs(args.demo_dir, exist_ok=True)
    # if args.eval_dir == "":
    #     kitti_visual_tool(args.data_root, args.demo_dir)

    height_order = True
    
    root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    folder_path = os.path.join(root_path,"data/rope3d-kitti/training/")
    map2id_path = os.path.join(root_path,"data/rope3d-kitti/map_token2id.json")
    generate_path = os.path.join(root_path,"data/rope3d/order_split/8_2_increase") 
    output_data_path = "outputs/rope3d_data_infomation/"
    camera_dict, image_dict, count_dict, intri_extri_denorm  = read_all_txt(os.path.join(folder_path,"calib"))
    height_dict = get_camera_height(intri_extri_denorm)
    print("height_dict",height_dict)
    get_all_intri_extri(intri_extri_denorm,os.path.join(root_path,output_data_path),height_dict)

    if height_order:
        train_list, test_list, split_camera_set= split_data_rope(image_dict, count_dict, height_dict)
    else:
        train_list, test_list ,split_camera_set = split_data_rope(image_dict, count_dict)

    
    ### 
    print("write_split------------------------------------------------------------------------------------------")
    write_split(root_path,map2id_path, train_list, test_list, generate_path, height_dict, split_camera_set)



    print("count_dict",count_dict)
