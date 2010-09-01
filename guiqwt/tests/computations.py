# -*- coding: utf-8 -*-
#
# Copyright © 2009-2010 CEA
# Pierre Raybaut
# Licensed under the terms of the CECILL License
# (see guiqwt/__init__.py for details)

"""Plot computations test"""

from guiqwt.plot import CurvePlotDialog
from guiqwt.builder import make

SHOW = True # Show test in GUI-based test launcher

def plot( *items ):
    win = CurvePlotDialog(edit=False, toolbar=True)
    plot = win.get_plot()
    for item in items:
        plot.add_item(item)
    win.show()
    win.exec_()

def test():
    """Test"""
    # -- Create QApplication
    import guidata
    guidata.qapplication()
    # --
    from numpy import linspace, sin, trapz
    x = linspace(-10, 10, 1000)
    y = sin(sin(sin(x)))

    curve = make.curve(x, y, "ab", "b")
    range = make.range(-2, 2)
    disp1 = make.computation(range, "BL", "trapz=%f",
                             curve, lambda x,y: trapz(y,x))
    disp2 = make.computations(range, "TL",
                              [(curve, "min=%.5f", lambda x,y: y.min()),
                               (curve, "max=%.5f", lambda x,y: y.max()),
                               (curve, "avg=%.5f", lambda x,y: y.mean())])
    legend = make.legend("TR")
    plot( curve, range, disp1, disp2, legend)

if __name__ == "__main__":
    test()