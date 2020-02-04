import torch.nn as nn
import torch
# import torch.nn.functional as F
from models.se_resnext import se_resnext_50, se_resnext_101
from models.resnext_cbam import resnext50
from models.senet_backbone import senet50

# import torchvision
# torchvision.models.squeezenet1_0()

class Aff2Net(nn.Module):
    def __init__(self, initial_ses, arc_face, backbone):
        super(Aff2Net, self).__init__()
        if backbone == "resnext":
            self.backbone = resnext50()    # with cbam
            # self.backbone.load_state_dict(torch.load("NewDict/ResNext50_checkpoint_best.pth.tar"), strict=False)
        # strict=False: pretrained dict for all convs(backbone) and discard fc layers
        else:
            self.backbone = senet50()
            # self.backbone.load_state_dict(torch.load("NewDict/se50_2oft_weight.pkl"), strict=False)
        # for param in self.backbone.parameters():
        #     param.requires_grad = False
        #     # print(type(param.data), param.size())
        # print("backbone freeze")
        self.avgpool = nn.AvgPool2d(7, stride=1)
        # # fine-tuned layers
        gap_conv = nn.Conv2d(512 * 4, 512, kernel_size=1)
        self.gap_feature = nn.Sequential(nn.Dropout(0.5),
                                         gap_conv,
                                         nn.LeakyReLU(inplace=True),
                                         nn.AdaptiveAvgPool2d((1, 1))
                                         )
        gmp_conv = nn.Conv2d(512 * 4, 512, kernel_size=1)
        self.gmp_feature = nn.Sequential(nn.Dropout(0.5),
                                         gmp_conv,
                                         nn.LeakyReLU(inplace=True),
                                         nn.AdaptiveMaxPool2d((1, 1))
                                         )
        self.au_classifier = nn.Linear(1024, 8)
        self.arc_face = arc_face
        if arc_face is True:
            self.expr_classifier = nn.Sequential(nn.Linear(1024, 256),
                                                 nn.BatchNorm1d(256),
                                                 nn.ReLU(inplace=True),
                                                 nn.Dropout(0.5)
                                                 )
        else:
            self.expr_classifier = nn.Linear(1024, 7)
            # expr_conv = nn.Conv2d(512 * 4, 7, kernel_size=1)
            # self.expr_classifier = nn.Sequential(nn.Dropout(0.5),
            #                                      expr_conv,
            #                                      nn.ReLU(inplace=True),
            #                                      nn.AdaptiveAvgPool2d((1, 1))
            #                                      )
        # au_conv = nn.Conv2d(512 * 4, 8, kernel_size=1)
        # self.au_classifier = nn.Sequential(nn.Dropout(0.5),
        #                                    au_conv,
        #                                    nn.ReLU(inplace=True),
        #                                    nn.AdaptiveAvgPool2d((1, 1))
        #                                    )
        self.va_regression = nn.Linear(1024, 2)
        # self.tanh = nn.Tanh()
        # print("tanh on")
        assert len(initial_ses) == 3
        self._weight_va = nn.Parameter(torch.tensor([initial_ses[0]], dtype=torch.float), requires_grad=True)
        self._weight_au = nn.Parameter(torch.tensor([initial_ses[1]], dtype=torch.float), requires_grad=True)
        self._weight_expr = nn.Parameter(torch.tensor([initial_ses[2]], dtype=torch.float), requires_grad=True)

    @staticmethod
    def _make_fclayer_(input_channel, out_channel):
        return nn.Sequential(nn.Linear(input_channel, 256),
                             nn.BatchNorm1d(256),
                             nn.LeakyReLU(inplace=True),
                             nn.Dropout(0.5),
                             nn.Linear(256, out_channel))

    def forward(self, x):
        x = self.backbone(x)    # bs, 2048, 7, 7
        # print("x size:", x.size())
        x_gap = self.gap_feature(x)
        x_gmp = self.gmp_feature(x)
        x = torch.cat((x_gap, x_gmp), 1)
        x = torch.flatten(x, 1)
        # print("x size:", x.size())
        # x = self.avgpool(x)
        # x = x.view(x.size(0), -1)
        # y_va = self.va_layer(x)
        # y_aus = self.aus_layer(x)
        # y_expr = self.expr_layer(x)
        # if self.arc_face is True:
        #     x_expr = self.conv_bn(x)
        #     x_expr = self.avgpool(x_expr)
        #     y_expr = self.expr_classifier(x_expr.view(x_expr.size(0), -1))
        # else:
        y_expr = self.expr_classifier(x)
        y_va = self.va_regression(x)
        # y_va = self.tanh(y_va)
        y_aus = self.au_classifier(x)
        # y_aus = y_aus.view(y_aus.size(0), 8)
        return y_va, y_aus, y_expr

    def get_loss_weights(self) -> (nn.Parameter, nn.Parameter, nn.Parameter):
        """Returns the loss weight parameters (s in the paper)."""
        return self._weight_va, self._weight_au, self._weight_expr


def aff2net(**kwargs):
    """Constructs a SENet-50 model.
    """
    model = Aff2Net(**kwargs)
    return model
