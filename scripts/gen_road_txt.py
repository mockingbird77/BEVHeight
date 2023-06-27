import json
import glob
import os
import numpy as np
import yaml



def get_image_count(path):
    folder_path = os.path.join(path, 'image_2')
    pattern = '*.png'  # 匹配PNG图像文件

    # 使用glob模块统计匹配的文件数量
    file_list = glob.glob(os.path.join(folder_path, pattern))
    count = len(file_list)
    return count

def gen_intri(path):# 读取JSON文件

    json_name = os.path.basename(path) + ".json"
    json_file = os.path.join(path,json_name)
    with open(json_file, 'r') as file:
        data = json.load(file)

    # 提取'intrinsic'数据
    intrinsic = data['intrinsic']

    intrinsic_p2_str = 'P2: {:.6f} {:.6f} {:.6f} 0 {:.6f} {:.6f} {:.6f} {:.6f} 0 0 1 0'.format(
        intrinsic[0][0], intrinsic[0][1], intrinsic[0][2],
        intrinsic[1][0], intrinsic[1][1], intrinsic[1][2],
        intrinsic[2][0], intrinsic[2][1])


    # 创建'calib'文件夹（如果不存在）
    calib_folder = os.path.join(path,'calib')
    if not os.path.exists(calib_folder):
        os.makedirs(calib_folder)


    count = get_image_count(path)
    # 写入count个文本文件
    for i in range(count):
        # 生成文件名（6位数字，从000000开始递增）

        
        filename = f'{i:06d}.txt'

        # 构建文件路径
        filepath = os.path.join(calib_folder, filename)

        # 写入'intrinsic'数据到文本文件
        with open(filepath, 'w') as file:
            file.write(intrinsic_p2_str)

    print("intri finished")


def get_Atocamera(path):# 读取JSON文件
    json_name = os.path.basename(path) + ".json"
    json_file = os.path.join(path,json_name)
    with open(json_file, 'r') as file:
        data = json.load(file)

    # 提取'extrinsic'数据
    extrinsic = np.array(data['extrinsic'])
    print("extrinsic",extrinsic)

    extrinsic[2,3] = extrinsic[2,3]+71

    print("extrinsic2",extrinsic)

    R_camera2A = extrinsic[:3, :3]
    T_camera2A = extrinsic[:3, 3]


    R_A2camera = np.linalg.inv(R_camera2A)
    T_A2camera = -np.dot(R_A2camera, T_camera2A)
    Tr_A2camera = np.eye(4)
    Tr_A2camera[:3, :3] = R_A2camera
    Tr_A2camera[:3, 3] = T_A2camera

    return  Tr_A2camera


def z_fromxy(denorm,x, y):
    # Ax + By + Cz + D = 0
    if(denorm[2] != 0):
        z =  -(denorm[0] * x + denorm[1] * y + denorm[3]) /denorm[2] 
    else:
        print("error, the ground place Ax + By + Cz + D = 0, C = 0")
        exit()
    return np.array([x,y,z,1])

def d_from(point_camera,normal_cam):
    d = -(point_camera[0]*normal_cam[0] + point_camera[1]*normal_cam[1] + point_camera[2]*normal_cam[2])
    return d

# version 1
# def get_denormInCam(denormA, Tr_A2camera):
    
#     normal_A = np.array([denormA[0], denormA[1], denormA[2], 0])
#     D_A =  np.array([0,0,0,denormA[3]])
#     print("D_A",denormA)

#     oldD = denormA[3]

#     normal_camera = np.dot(Tr_A2camera, normal_A)[:3] 
#     normal_camera = normal_camera / np.sqrt(normal_camera[0]**2 + normal_camera[1]**2 + normal_camera[2]**2)
#     print("tr_A2camera",Tr_A2camera)
#     print("DA",D_A)
#     D_camera = np.dot(Tr_A2camera, D_A)[3] 
#     print("np.dot(Tr_A2camera, D_A)",np.dot(Tr_A2camera, D_A))

#     denorm_camera =np.array([normal_camera[0], normal_camera[1], normal_camera[2], D_camera])

#     return denorm_camera

# version 2
def get_denormInCam(denormA, Tr_A2camera):
    # Tr_A2camera 4*4

    normal_A = np.array([denormA[0], denormA[1], denormA[2], 0])
    D_A =  np.array([0,0,0,denormA[3]])
    print("D_A",denormA)

    oldD = denormA[3]

    normal_camera = np.dot(Tr_A2camera, normal_A)[:3] 
    normal_camera = normal_camera / np.sqrt(normal_camera[0]**2 + normal_camera[1]**2 + normal_camera[2]**2)
    print("tr_A2camera",Tr_A2camera)
    print("DA",D_A)

    pointA  = z_fromxy(denormA,1,1)
    point_camera = np.dot(Tr_A2camera,pointA)
    D_camera = d_from(point_camera,normal_camera)

    #D_camera = np.dot(Tr_A2camera, D_A)[3] 
    print("np.dot(Tr_A2camera, D_A)",np.dot(Tr_A2camera, D_A))

    denorm_camera =np.array([normal_camera[0], normal_camera[1], normal_camera[2], D_camera])

    return denorm_camera


# def gen_denorm(path):
#     denorm_path = os.path.join(path,"denorm.txt")
#     with open(denorm_path, 'r') as file:
#         content = file.readline().strip()  # 读取第一行内容并去除换行符
#         denorm_A = [float(x) for x in content.split()]  # 将内容按空格分割并转换为浮点数列表
    
#     Tr_A2camera = get_Atocamera(path)

#     denorm_camera = get_denormInCam(denorm_A,Tr_A2camera)
#     print("denorm_camera",denorm_camera)
#     count = get_image_count(path)
#         # 写入count个文本文件

#     denorm_folder = os.path.join(path, 'denorm')
#     if not os.path.exists(denorm_folder):
#         os.makedirs(denorm_folder)
#     content = "{:.10f}".format(denorm_camera[0]) + " ".join("{:.10f}".format(x) for x in denorm_camera[1:])  # 将数组元素转换为字符串并用空格连接
#     for i in range(count):
#         # 生成文件名（6位数字，从000000开始递增）
#         filename = f'{i:06d}.txt'

#         # 构建文件路径
#         filepath = os.path.join(denorm_folder, filename)

#         with open(filepath, 'w') as file:
#             file.write(content)
#     print("denorm finished")

def gen_denorm(path):
    denorm_path = os.path.join(path,"denorm.txt")
    with open(denorm_path, 'r') as file:
        content = file.readline().strip()  # 读取第一行内容并去除换行符
        denorm_A = [float(x) for x in content.split()]  # 将内容按空格分割并转换为浮点数列表
    
    Tr_A2camera = get_Atocamera(path)

    denorm_camera = get_denormInCam(denorm_A,Tr_A2camera)
    print("denorm_camera",denorm_camera)
    count = get_image_count(path)
        # 写入count个文本文件

    denorm_folder = os.path.join(path, 'denorm')
    print("denorm_folder",denorm_folder)
    if not os.path.exists(denorm_folder):
        os.makedirs(denorm_folder)
    print("denorm_camera",denorm_camera)
    content = " ".join("{:.10f}".format(x) for x in denorm_camera[0:])  # 将数组元素转换为字符串并用空格连接

    print("content",content)
    for i in range(count):
        # 生成文件名（6位数字，从000000开始递增）
        filename = f'{i:06d}.txt'

        # 构建文件路径
        filepath = os.path.join(denorm_folder, filename)
        
        with open(filepath, 'w') as file:
            file.write(content)
    print("denorm finished")


def gen_label(path,extend):
    count = get_image_count(path)
        # 写入count个文本文件

    denorm_folder = os.path.join(path, extend)
    if not os.path.exists(denorm_folder):
        os.makedirs(denorm_folder)
    content = "car 0 0 4.635809173730361 960.387817 650.730469 1158.447998 864.502381 0.882855 1.75447 4.209558 1.15997194308 2.22240749021 23.168408123 4.68583437001"
    for i in range(count):
        # 生成文件名（6位数字，从000000开始递增）
        filename = f'{i:06d}.txt'

        # 构建文件路径
        filepath = os.path.join(denorm_folder, filename)

        with open(filepath, 'w') as file:
            file.write(content)
    print(extend + " finished")

def gen_yaml(path,extend):

    count = get_image_count(path)
        # 写入count个文本文件

    denorm_folder = os.path.join(path, extend)
    if not os.path.exists(denorm_folder):
        os.makedirs(denorm_folder)
    data = {
        'child_frame_id': 'camera1',
        'header': {
            'frame_id': 'world',
            'seq': 0,
            'stamp': {
                'nsecs': 0,
                'secs': 0
            }
        },
        'matched_points': 0
    }
    for i in range(count):
        # 生成文件名（6位数字，从000000开始递增）
        filename = f'{i:06d}.yaml'

        # 构建文件路径
        filepath = os.path.join(denorm_folder, filename)

        with open(filepath, 'w') as file:
            yaml.dump(data,file)
    print(extend+ " finished")


def write_split(path, split):
    start_number = 0
    end_number = get_image_count(path)-1

    # 指定要保存的文件路径
    file_path = os.path.join(path, split+ ".txt")

    # 生成数字并写入txt文件
    with open(file_path, 'w') as file:
        for number in range(start_number, end_number + 1):
            file.write(str(number).zfill(6) + '\n')

def main():
    path = "/data/bevheight/BEVHeight/data/road/314"
    gen_intri(path)
    gen_denorm(path)
    gen_label(path,"label_2")
    gen_yaml(path,"extrinsics")
    write_split(path, "val")

if __name__ == '__main__':
    main()