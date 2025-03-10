# Copyright (c) Megvii Inc. All rights reserved.
import numpy as np

import torch
import torch.nn.functional as F
from mmcv.cnn import build_conv_layer
from mmdet3d.models import build_neck
from mmdet.models import build_backbone
from mmdet.models.backbones.resnet import BasicBlock
from torch import nn

from ops.voxel_pooling import voxel_pooling

__all__ = ['LSSFPN']


class _ASPPModule(nn.Module):
    def __init__(self, inplanes, planes, kernel_size, padding, dilation,
                 BatchNorm):
        super(_ASPPModule, self).__init__()
        self.atrous_conv = nn.Conv2d(inplanes,
                                     planes,
                                     kernel_size=kernel_size,
                                     stride=1,
                                     padding=padding,
                                     dilation=dilation,
                                     bias=False)
        self.bn = BatchNorm(planes)
        self.relu = nn.ReLU()

        self._init_weight()

    def forward(self, x):
        x = self.atrous_conv(x)
        x = self.bn(x)

        return self.relu(x)

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


class ASPP(nn.Module):
    def __init__(self, inplanes, mid_channels=256, BatchNorm=nn.BatchNorm2d):
        super(ASPP, self).__init__()

        dilations = [1, 6, 12, 18]

        self.aspp1 = _ASPPModule(inplanes,
                                 mid_channels,
                                 1,
                                 padding=0,
                                 dilation=dilations[0],
                                 BatchNorm=BatchNorm)
        self.aspp2 = _ASPPModule(inplanes,
                                 mid_channels,
                                 3,
                                 padding=dilations[1],
                                 dilation=dilations[1],
                                 BatchNorm=BatchNorm)
        self.aspp3 = _ASPPModule(inplanes,
                                 mid_channels,
                                 3,
                                 padding=dilations[2],
                                 dilation=dilations[2],
                                 BatchNorm=BatchNorm)
        self.aspp4 = _ASPPModule(inplanes,
                                 mid_channels,
                                 3,
                                 padding=dilations[3],
                                 dilation=dilations[3],
                                 BatchNorm=BatchNorm)

        self.global_avg_pool = nn.Sequential(
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Conv2d(inplanes, mid_channels, 1, stride=1, bias=False),
            BatchNorm(mid_channels),
            nn.ReLU(),
        )
        self.conv1 = nn.Conv2d(int(mid_channels * 5),
                               mid_channels,
                               1,
                               bias=False)
        self.bn1 = BatchNorm(mid_channels)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.5)
        self._init_weight()

    def forward(self, x):
        x1 = self.aspp1(x)
        x2 = self.aspp2(x)
        x3 = self.aspp3(x)
        x4 = self.aspp4(x)
        x5 = self.global_avg_pool(x)
        x5 = F.interpolate(x5,
                           size=x4.size()[2:],
                           mode='bilinear',
                           align_corners=True)
        x = torch.cat((x1, x2, x3, x4, x5), dim=1)

        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)

        return self.dropout(x)

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


class Mlp(nn.Module):
    def __init__(self,
                 in_features,
                 hidden_features=None,
                 out_features=None,
                 act_layer=nn.ReLU,
                 drop=0.0):
        super().__init__()
        out_features = out_features or in_features
        hidden_features = hidden_features or in_features
        self.fc1 = nn.Linear(in_features, hidden_features)
        self.act = act_layer()
        self.drop1 = nn.Dropout(drop)
        self.fc2 = nn.Linear(hidden_features, out_features)
        self.drop2 = nn.Dropout(drop)

    def forward(self, x):
        x = self.fc1(x)
        x = self.act(x)
        x = self.drop1(x)
        x = self.fc2(x)
        x = self.drop2(x)
        return x


class SELayer(nn.Module):
    def __init__(self, channels, act_layer=nn.ReLU, gate_layer=nn.Sigmoid):
        super().__init__()
        self.conv_reduce = nn.Conv2d(channels, channels, 1, bias=True)
        self.act1 = act_layer()
        self.conv_expand = nn.Conv2d(channels, channels, 1, bias=True)
        self.gate = gate_layer()

    def forward(self, x, x_se):
        x_se = self.conv_reduce(x_se)
        x_se = self.act1(x_se)
        x_se = self.conv_expand(x_se)
        return x * self.gate(x_se)


class PositionalLayer(nn.Module):
    def __init__(self, in_channels, out_channels, act_layer=nn.ReLU, gate_layer=nn.Sigmoid):
        super().__init__()
        self.conv_reduce = nn.Conv2d(in_channels, out_channels, 1, bias=True)
        self.act1 = act_layer()
        self.conv_expand = nn.Conv2d(out_channels, out_channels, 1, bias=True)
        self.gate = gate_layer()

    def forward(self, x, x_se):
        x_se = self.conv_reduce(x_se)
        x_se = self.act1(x_se)
        x_se = self.conv_expand(x_se)
        return x + self.gate(x_se)


# 生成height的特征以及image feature的概率cat到了一起
class HeightNet(nn.Module):
    def __init__(self, in_channels, mid_channels, context_channels,
                 height_channels):
        super(HeightNet, self).__init__()
        self.reduce_conv = nn.Sequential(
            nn.Conv2d(in_channels,
                      mid_channels,
                      kernel_size=3,
                      stride=1,
                      padding=1),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
        )
        self.context_conv = nn.Conv2d(mid_channels,
                                      context_channels,
                                      kernel_size=1,
                                      stride=1,
                                      padding=0)
        self.bn = nn.BatchNorm1d(27)
        self.height_mlp = Mlp(27, mid_channels, mid_channels)
        self.height_se = SELayer(mid_channels)  # NOTE: add camera-aware
        self.context_mlp = Mlp(27, mid_channels, mid_channels)
        self.context_se = SELayer(mid_channels)  # NOTE: add camera-aware

        self.direction_mlp = Mlp(27,mid_channels,mid_channels)
        
        self.context_position = PositionalLayer(27,mid_channels) 
        self.height_position = PositionalLayer(27,mid_channels) 

        self.height_conv = nn.Sequential(
            BasicBlock(mid_channels, mid_channels),
            BasicBlock(mid_channels, mid_channels),
            BasicBlock(mid_channels, mid_channels),
            ASPP(mid_channels, mid_channels),
            build_conv_layer(cfg=dict(
                type='DCN',
                in_channels=mid_channels,
                out_channels=mid_channels,
                kernel_size=3,
                padding=1,
                groups=4,
                im2col_step=128,
            )),
            
        )
        self.height_layer = nn.Conv2d(mid_channels,
                      height_channels,
                      kernel_size=1,
                      stride=1,
                      padding=0)

    def forward(self, x, mats_dict, pos_en):
        intrins = mats_dict['intrin_mats'][:, 0:1, ..., :3, :3]
        batch_size = intrins.shape[0]
        num_cams = intrins.shape[2]
        ida = mats_dict['ida_mats'][:, 0:1, ...]
        sensor2ego = mats_dict['sensor2ego_mats'][:, 0:1, ..., :3, :]
        bda = mats_dict['bda_mat'].view(batch_size, 1, 1, 4,
                                        4).repeat(1, 1, num_cams, 1, 1)
        mlp_input = torch.cat(
            [
                torch.stack(
                    [
                        intrins[:, 0:1, ..., 0, 0],
                        intrins[:, 0:1, ..., 1, 1],
                        intrins[:, 0:1, ..., 0, 2],
                        intrins[:, 0:1, ..., 1, 2],
                        ida[:, 0:1, ..., 0, 0],
                        ida[:, 0:1, ..., 0, 1],
                        ida[:, 0:1, ..., 0, 3],
                        ida[:, 0:1, ..., 1, 0],
                        ida[:, 0:1, ..., 1, 1],
                        ida[:, 0:1, ..., 1, 3],
                        bda[:, 0:1, ..., 0, 0],
                        bda[:, 0:1, ..., 0, 1],
                        bda[:, 0:1, ..., 1, 0],
                        bda[:, 0:1, ..., 1, 1],
                        bda[:, 0:1, ..., 2, 2],
                    ],
                    dim=-1,
                ),
                sensor2ego.view(batch_size, 1, num_cams, -1),
            ],
            -1,
        )
        mlp_input = self.bn(mlp_input.reshape(-1, mlp_input.shape[-1]))
        x = self.reduce_conv(x)
        context_se = self.context_mlp(mlp_input)[..., None, None]
        context = self.context_se(x, context_se)
        context = self.context_position(x,pos_en)
        context = self.context_conv(context)
        


        height_se = self.height_mlp(mlp_input)[..., None, None]
        height = self.height_se(x, height_se)
        height = self.height_position(x,pos_en)

        height = self.height_conv(height)
        height = self.height_layer(height)

        return torch.cat([height, context], dim=1)


class LSSFPN(nn.Module):
    def __init__(self, x_bound, y_bound, z_bound, d_bound, final_dim,
                 downsample_factor, output_channels, img_backbone_conf,
                 img_neck_conf, height_net_conf):
        """Modified from `https://github.com/nv-tlabs/lift-splat-shoot`.

        Args:
            x_bound (list): Boundaries for x.
            y_bound (list): Boundaries for y.
            z_bound (list): Boundaries for z.
            d_bound (list): Boundaries for d.
            final_dim (list): Dimension for input images.
            downsample_factor (int): Downsample factor between feature map
                and input image.
            output_channels (int): Number of channels for the output
                feature map.
            img_backbone_conf (dict): Config for image backbone.
            img_neck_conf (dict): Config for image neck.
            height_net_conf (dict): Config for height net.
        """

        super(LSSFPN, self).__init__()
        self.downsample_factor = downsample_factor
        self.d_bound = d_bound
        self.final_dim = final_dim
        self.output_channels = output_channels

        self.multires = 4
        embed_kwargs = {
                'include_input' : True,
                'input_dims' : 3,
                'max_freq_log2' : self.multires-1,
                'num_freqs' : self.multires,
                'log_sampling' : True,
                'periodic_fns' : [torch.sin, torch.cos],
        }
    
        self.embedder_obj = Embedder(**embed_kwargs)


        self.register_buffer(
            'voxel_size',
            torch.Tensor([row[2] for row in [x_bound, y_bound, z_bound]]))
        self.register_buffer(
            'voxel_coord',
            torch.Tensor([
                row[0] + row[2] / 2.0 for row in [x_bound, y_bound, z_bound]
            ]))
        self.register_buffer(
            'voxel_num',
            torch.LongTensor([(row[1] - row[0]) / row[2]
                              for row in [x_bound, y_bound, z_bound]]))
        
        # why use register_buffer here? 
        self.register_buffer('frustum', self.create_frustum())
        
        # rays_base
        self.register_buffer('rays_base', self.create_rays_base())
        self.height_channels, _, _, _ = self.frustum.shape
        
        self.img_backbone = build_backbone(img_backbone_conf)
        self.img_neck = build_neck(img_neck_conf)
        self.height_net = self._configure_height_net(height_net_conf)

        self.img_neck.init_weights()
        self.img_backbone.init_weights()

    def _configure_height_net(self, height_net_conf):
        return HeightNet(
            height_net_conf['in_channels'],
            height_net_conf['mid_channels'],
            self.output_channels,
            self.height_channels,
        )
    

    def create_rays_base(self):
    
        ogfH, ogfW = self.final_dim
        H, W = ogfH // self.downsample_factor, ogfW // self.downsample_factor
        # deal with the downsample_factor here
        i, j = torch.meshgrid(torch.linspace(0, ogfW-1, W), torch.linspace(0, ogfH-1, H))  # pytorch's meshgrid has indexing='ij'
        i = i.t()
        j = j.t()
        rays_base = torch.stack([i, j, torch.ones_like(i),torch.ones_like(i)], -1)

        return rays_base
    

    def create_frustum(self):
        """Generate frustum"""
        # make grid in image plane
        ogfH, ogfW = self.final_dim
        fH, fW = ogfH // self.downsample_factor, ogfW // self.downsample_factor
        
        # DID
        alpha = 1.5
        d_coords = np.arange(self.d_bound[2]) / self.d_bound[2]
        d_coords = np.power(d_coords, alpha)
        d_coords = self.d_bound[0] + d_coords * (self.d_bound[1] - self.d_bound[0])
        d_coords = torch.tensor(d_coords, dtype=torch.float).view(-1, 1, 1).expand(-1, fH, fW)
        
        D, _, _ = d_coords.shape
        # deal with the downsample_factor here
        x_coords = torch.linspace(0, ogfW - 1, fW, dtype=torch.float).view(
            1, 1, fW).expand(D, fH, fW)
        y_coords = torch.linspace(0, ogfH - 1, fH,
                                  dtype=torch.float).view(1, fH,
                                                          1).expand(D, fH, fW)
        paddings = torch.ones_like(d_coords)

        # D x H x W x 3 --> D H W 4
        frustum = torch.stack((x_coords, y_coords, d_coords, paddings), -1)
        return frustum

    # height
    def height2localtion(self, points, sensor2ego_mat, sensor2virtual_mat, intrin_mat, reference_heights):
        batch_size, num_cams, _, _ = sensor2ego_mat.shape
        reference_heights = reference_heights.view(batch_size, num_cams, 1, 1, 1, 1,
                                                   1).repeat(1, 1, points.shape[2], points.shape[3], points.shape[4], 1, 1)
        height = -1 * points[:, :, :, :, :, 2, :] + reference_heights[:, :, :, :, :, 0, :]
        # 这一块是高度的
        points_const = points.clone()
        points_const[:, :, :, :, :, 2, :] = 10
        points_const = torch.cat(
            (points_const[:, :, :, :, :, :2] * points_const[:, :, :, :, :, 2:3],
             points_const[:, :, :, :, :, 2:]), 5)
        combine_virtual = sensor2virtual_mat.matmul(torch.inverse(intrin_mat))
        points_virtual = combine_virtual.view(batch_size, num_cams, 1, 1, 1, 4, 4).matmul(points_const)
        ratio = height[:, :, :, :, :, 0] / points_virtual[:, :, :, :, :, 1, 0]
        ratio = ratio.view(batch_size, num_cams, ratio.shape[2], ratio.shape[3], ratio.shape[4], 1, 1).repeat(1, 1, 1, 1, 1, 4, 1)
        points = points_virtual * ratio

        points[:, :, :, :, :, 3, :] = 1
        combine_ego = sensor2ego_mat.matmul(torch.inverse(sensor2virtual_mat))
        points = combine_ego.view(batch_size, num_cams, 1, 1, 1, 4,
                              4).matmul(points)
        return points
    

    # 锥点由图像坐标系向ego坐标系进行坐标转化
    def get_geometry(self, sensor2ego_mat, sensor2virtual_mat, intrin_mat, ida_mat, reference_heights, bda_mat):
        """Transfer points from camera coord to ego coord.

        Args:
            rots(Tensor): Rotation matrix from camera to ego.
            trans(Tensor): Translation matrix from camera to ego.
            intrins(Tensor): Intrinsic matrix.
            post_rots_ida(Tensor): Rotation matrix for ida.     图像数据增广产生的旋转矩阵 
            post_trans_ida(Tensor): Translation matrix for ida  图像数据增广产生的平移矩阵
            post_rot_bda(Tensor): Rotation matrix for bda.      
            intrin_mat ([4, 1, 4, 4])
            ida_mat ([4, 1, 4, 4])
            bda_mat ([4, 4, 4])
            sensor2virtual_mat ([4, 1, 4, 4])
            sensor2ego_mat ([4, 1, 4, 4])

        Returns:
            Tensors: points ego coord.
        """
        batch_size, num_cams, _, _ = sensor2ego_mat.shape

        # undo post-transformation
        # B x N x D x H x W x 3
        points = self.frustum  # points torch.Size([180, 54, 96, 4])

        ida_mat = ida_mat.view(batch_size, num_cams, 1, 1, 1, 4, 4)  
        #  去除points数据增广产生的影响 
        points = ida_mat.inverse().matmul(points.unsqueeze(-1)) # points torch.Size([4, 1, 180, 54, 96, 4, 1 ]) 


        #  将points 从 camera 坐标系转到 ego 坐标系
        points = self.height2localtion(points, sensor2ego_mat, sensor2virtual_mat, intrin_mat, reference_heights) 

        if bda_mat is not None:
            bda_mat = bda_mat.unsqueeze(1).repeat(1, num_cams, 1, 1).view(
                batch_size, num_cams, 1, 1, 1, 4, 4)
            points = (bda_mat @ points).squeeze(-1)
        else:
            points = points.squeeze(-1)
        
        # Returns B x N x D x H x W x 3
        # Returns 像素在激光坐标系中的3D坐标
        return points[..., :3]
    
    def get_rays_dir(self,c2i, c2w, ida):
        batch_size, num_cams, _, _ = c2i.shape
        rays_base = self.rays_base  #r torch.Size([54, 96, 4])
        # Todo broad cast  broad cast from tail to head
        
        # H  W  4  1
        ida = ida.view(batch_size, num_cams, 1, 1, 4, 4)  
        rays_imgdir = ida.inverse().matmul((rays_base.unsqueeze(-1)))

        i2c = torch.inverse(c2i)

        
        #  H W 4
        i2c = i2c.view(batch_size, num_cams, 1, 1, 4, 4)  
        dirs = i2c.matmul(rays_imgdir)

        c2w = c2w.view(batch_size, num_cams, 1, 1, 4, 4)  
        rays_d= (c2w.matmul(dirs)).squeeze(-1)[...,:3]
        
        # TODO  
        # 0. normalize the rays direction 
        # 1. get the directional encoding 
        # 2. add the encoding to the conv layer 

        # rays_d  batch_size cam_num h w 3
        return  rays_d

    def get_cam_feats(self, imgs):
        """Get feature maps from images."""
        batch_size, num_sweeps, num_cams, num_channels, imH, imW = imgs.shape

        imgs = imgs.flatten().view(batch_size * num_sweeps * num_cams,
                                   num_channels, imH, imW)
        img_feats = self.img_neck(self.img_backbone(imgs))[0]
        img_feats = img_feats.reshape(batch_size, num_sweeps, num_cams,
                                      img_feats.shape[1], img_feats.shape[2],
                                      img_feats.shape[3])
        return img_feats

    def _forward_height_net(self, feat, mats_dict, pos_en):
        return self.height_net(feat, mats_dict,pos_en)

    def _forward_voxel_net(self, img_feat_with_height):
        return img_feat_with_height

    def _forward_single_sweep(self,
                              sweep_index,
                              sweep_imgs,
                              mats_dict,
                              is_return_height=False):
        """Forward function for single sweep.

        Args:
            sweep_index (int): Index of sweeps.
            sweep_imgs (Tensor): Input images.
            mats_dict (dict):
                sensor2ego_mats(Tensor): Transformation matrix from
                    camera to ego with shape of (B, num_sweeps,
                    num_cameras, 4, 4).
                intrin_mats(Tensor): Intrinsic matrix with shape
                    of (B, num_sweeps, num_cameras, 4, 4).
                ida_mats(Tensor): Transformation matrix for ida with
                    shape of (B, num_sweeps, num_cameras, 4, 4).
                sensor2sensor_mats(Tensor): Transformation matrix
                    from key frame camera to sweep frame camera with
                    shape of (B, num_sweeps, num_cameras, 4, 4).
                bda_mat(Tensor): Rotation matrix for bda with shape
                    of (B, 4, 4).
            is_return_height (bool, optional): Whether to return height.
                Default: False.

        Returns:
            Tensor: BEV feature map.
        """
        batch_size, num_sweeps, num_cams, num_channels, img_height, \
            img_width = sweep_imgs.shape
        img_feats = self.get_cam_feats(sweep_imgs)  # [4, 1, 1, 512, 54, 96])  batch_size, num_sweeps, num_cams, num_channels, img_height, img_width

        # insert the direction here

        # 4 1 4 4    *     H w 4   =  4 1 H w 4  
        # 
        dirs = self.get_rays_dir( mats_dict['intrin_mats'][:, sweep_index, ...],mats_dict['sensor2ego_mats'][:, sweep_index, ...],mats_dict['ida_mats'][:, sweep_index, ...])


        dir_embbed = (self.embedder_obj.embed(dirs)).permute( 0, 1, 4, 2, 3)




        # 4 1 
        source_features = img_feats[:, 0, ...]      # batch_size, num_cams, num_channels, img_height, img_width
        
        

        height_feature = self._forward_height_net(
            source_features.reshape(batch_size * num_cams,
                                    source_features.shape[2],
                                    source_features.shape[3],
                                    source_features.shape[4]),
            mats_dict,
            dir_embbed.reshape(batch_size * num_cams,
                                    dir_embbed.shape[2],
                                    dir_embbed.shape[3],
                                    dir_embbed.shape[4])
        )


        # height_feature.shape torch.Size([4, 260, 54, 96]) the first 180 dim  is height  the last 80 is feature
    

        height = height_feature[:, :self.height_channels].softmax(1) # height.shape torch.Size([4, 180, 54, 96])   
        

        img_feat_with_height = height.unsqueeze(
            1) * height_feature[:, self.height_channels:(
                self.height_channels + self.output_channels)].unsqueeze(2)
        img_feat_with_height = self._forward_voxel_net(img_feat_with_height)      # img_feat_with_height.shape torch.Size([4, 80, 180, 54, 96])      

        # height features 

        img_feat_with_height = img_feat_with_height.reshape(
            batch_size,
            num_cams,
            img_feat_with_height.shape[1],
            img_feat_with_height.shape[2],
            img_feat_with_height.shape[3],
            img_feat_with_height.shape[4],
        )
                   # img_feat_with_height.shape [4, 1, 80, 180, 54, 96])

        # B x N x D x H x W x 3
        geom_xyz = self.get_geometry(
            mats_dict['sensor2ego_mats'][:, sweep_index, ...],
            mats_dict['sensor2virtual_mats'][:, sweep_index, ...],
            mats_dict['intrin_mats'][:, sweep_index, ...],
            mats_dict['ida_mats'][:, sweep_index, ...],
            mats_dict['reference_heights'][:, sweep_index, ...],
            mats_dict.get('bda_mat', None),
        )

        img_feat_with_height = img_feat_with_height.permute(0, 1, 3, 4, 5, 2)     # img_feat_with_height.shape [4, 1, 180, 54, 96, 80])
       
        geom_xyz = ((geom_xyz - (self.voxel_coord - self.voxel_size / 2.0)) /
                    self.voxel_size).int()

        feature_map = voxel_pooling(geom_xyz, img_feat_with_height.contiguous(),
                                   self.voxel_num.cuda())
        
        if is_return_height:
            return feature_map.contiguous(), height
  
        return feature_map.contiguous()

    def forward(self,
                sweep_imgs,
                mats_dict,
                timestamps=None,
                is_return_height=False):
        """Forward function.

        Args:
            sweep_imgs(Tensor): Input images with shape of (B, num_sweeps,
                num_cameras, 3, H, W).
            mats_dict(dict):
                sensor2ego_mats(Tensor): Transformation matrix from
                    camera to ego with shape of (B, num_sweeps,
                    num_cameras, 4, 4).
                intrin_mats(Tensor): Intrinsic matrix with shape
                    of (B, num_sweeps, num_cameras, 4, 4).
                ida_mats(Tensor): Transformation matrix for ida with
                    shape of (B, num_sweeps, num_cameras, 4, 4).
                sensor2sensor_mats(Tensor): Transformation matrix
                    from key frame camera to sweep frame camera with
                    shape of (B, num_sweeps, num_cameras, 4, 4).
                bda_mat(Tensor): Rotation matrix for bda with shape
                    of (B, 4, 4). 
            timestamps(Tensor): Timestamp for all images with the shape of(B,
                num_sweeps, num_cameras).

        Return:
            Tensor: bev feature map.
        """
        batch_size, num_sweeps, num_cams, num_channels, img_height, \
            img_width = sweep_imgs.shape

        key_frame_res = self._forward_single_sweep(
            0,
            sweep_imgs[:, 0:1, ...],
            mats_dict,
            is_return_height=is_return_height)
        if num_sweeps == 1:
            return key_frame_res

        key_frame_feature = key_frame_res[
            0] if is_return_height else key_frame_res

        ret_feature_list = [key_frame_feature]
        for sweep_index in range(1, num_sweeps):
            with torch.no_grad():
                feature_map = self._forward_single_sweep(
                    sweep_index,
                    sweep_imgs[:, sweep_index:sweep_index + 1, ...],
                    mats_dict,
                    is_return_height=False)
                ret_feature_list.append(feature_map)

        if is_return_height:
            return torch.cat(ret_feature_list, 1), key_frame_res[1]
        else:
            return torch.cat(ret_feature_list, 1)





# def get_rays_intri_torch(H, W, c2i, c2w, ida):
#     i, j = torch.meshgrid(torch.linspace(0, W-1, W), torch.linspace(0, H-1, H))  # pytorch's meshgrid has indexing='ij'
#     i = i.t()
#     j = j.t()
#     # dirs = torch.stack([(i-W*.5)/focal, -(j-H*.5)/focal, -torch.ones_like(i)], -1).to(device)
    
#     # H w 3
#     rays_imgdir = torch.stack([i, j, torch.ones_like(i)], -1)
#     print("intri c2i",c2i)
#     i2c = torch.inverse(c2i)
#     print("intri i2c",i2c)
#     dirs = torch.sum(dirs[..., np.newaxis, :] * i2c, -1)

#     # Rotate ray directions from camera frame to the world frame
#     rays_d = torch.sum(dirs[..., np.newaxis, :] * c2w[:3,:3], -1)  # dot product, equals to: [c2w.dot(dir) for dir in dirs]
#     # Translate camera frame's origin to the world frame. It is the origin of all rays.


#     # rays_o = c2w[:3,-1].expand(rays_d.shape)
#     return  rays_d



# nerf positional embedding 
class Embedder:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.create_embedding_fn()
        
    def create_embedding_fn(self):
        embed_fns = []
        d = self.kwargs['input_dims']
        out_dim = 0
        if self.kwargs['include_input']:
            embed_fns.append(lambda x : x)
            out_dim += d
            
        max_freq = self.kwargs['max_freq_log2']
        N_freqs = self.kwargs['num_freqs']
        
        if self.kwargs['log_sampling']:
            freq_bands = 2.**torch.linspace(0., max_freq, steps=N_freqs)
        else:
            freq_bands = torch.linspace(2.**0., 2.**max_freq, steps=N_freqs)
            
        for freq in freq_bands:
            for p_fn in self.kwargs['periodic_fns']:
                embed_fns.append(lambda x, p_fn=p_fn, freq=freq : p_fn(x * freq))
                out_dim += d
                    
        self.embed_fns = embed_fns
        self.out_dim = out_dim
        
    def embed(self, inputs):
        return torch.cat([fn(inputs) for fn in self.embed_fns], -1)
    
