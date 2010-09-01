# -*- coding: utf-8 -*-
#
# Copyright © 2009-2010 CEA
# Pierre Raybaut
# Licensed under the terms of the CECILL License
# (see guiqwt/__init__.py for details)

"""Renders a cross section chosen by a cross marker"""

import os.path as osp

from guiqwt.plot import ImagePlotDialog
from guiqwt.tools import AverageCrossSectionsTool
from guiqwt.builder import make

SHOW = True # Show test in GUI-based test launcher

def create_window():
    win = ImagePlotDialog(edit=False, toolbar=True,
                          wintitle="Cross sections test",
                          options=dict(show_xsection=True, show_ysection=True))
    win.resize(600, 600)
    win.register_tool(AverageCrossSectionsTool)
    return win

def test():
    """Test"""
    # -- Create QApplication
    import guidata
    guidata.qapplication()
    # --
    filename = osp.join(osp.dirname(__file__), "brain.png")
    win = create_window()
    image = make.image(filename=filename, colormap="bone")
    plot = win.get_plot()
    plot.add_item(image)
    win.exec_()

if __name__ == "__main__":
    test()