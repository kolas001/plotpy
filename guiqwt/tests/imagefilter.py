# -*- coding: utf-8 -*-
#
# Copyright © 2009-2010 CEA
# Pierre Raybaut
# Licensed under the terms of the CECILL License
# (see guiqwt/__init__.py for details)

"""Image filter demo"""

from scipy.ndimage import gaussian_filter

from guiqwt.plot import ImagePlotDialog
from guiqwt.builder import make

SHOW = True # Show test in GUI-based test launcher

def imshow(x, y, data, filter_area, yreverse=True):
    win = ImagePlotDialog(edit=False, toolbar=True,
                          wintitle="Image filter demo",
                          options=dict(xlabel="x (cm)", ylabel="y (cm)",
                                       yreverse=yreverse))
    image = make.xyimage(x, y, data)
    plot = win.get_plot()
    plot.add_item(image)
    xmin, xmax, ymin, ymax = filter_area
    flt = make.imagefilter(xmin, xmax, ymin, ymax, image,
                           filter=lambda x, y, data: gaussian_filter(data, 5))
    plot.add_item(flt, z=1)
    plot.replot()
    win.show()
    win.exec_()

def test():
    """Test"""
    # -- Create QApplication
    import guidata
    guidata.qapplication()
    # --
    from guiqwt.tests.imagexy import compute_image
    imshow(*compute_image(), filter_area=(-3., -1., 0., 2.), yreverse=False)
    # --
    import os.path as osp, numpy as np
    from guiqwt.io import imagefile_to_array
    filename = osp.join(osp.dirname(__file__), "brain.png")
    data = imagefile_to_array(filename)
    x = np.linspace(0, 30., data.shape[1])
    y = np.linspace(0, 30., data.shape[0])
    imshow(x, y, data, filter_area=(10, 20, 5, 15))

if __name__ == "__main__":
    test()