import os

folder_path = "/data/bevheight/BEVHeight/data/road/314/image_2"  # 文件夹路径

# 获取文件夹中的所有文件
file_list = sorted(os.listdir(folder_path))

# 遍历文件列表
for i, filename in enumerate(file_list):
    print(filename)
    new_filename = f"{i:06d}.png"  # 生成新的文件名，如 "000000.png"
    os.rename(os.path.join(folder_path, filename), os.path.join(folder_path, new_filename))