# -*- coding: utf-8 -*-
#
# Copyright © 2011 CEA
# Pierre Raybaut
# Licensed under the terms of the CECILL License
# (see plotpy/__init__.py for details)

"""plotpy plot benchmarking"""

from __future__ import print_function

SHOW = False # Show test in GUI-based test launcher


import time
import numpy as np

from plotpy.qt.QtGui import QApplication

from plotpy.plot import CurveWindow, ImageWindow
from plotpy.builder import make


class BaseBM(object):
    """Benchmark object"""
    MAKE_FUNC = None
    WIN_CLASS = None
    
    def __init__(self, name, nsamples, **options):
        self.name = name
        self.nsamples = nsamples
        self.options = options
        self._item = None

    def compute_data(self):
        raise NotImplementedError
        
    def make_item(self):
        data = self.compute_data()
        self._item = self.MAKE_FUNC(*data, **self.options)
        
    def add_to_plot(self, plot):
        assert self._item is not None
        plot.add_item(self._item)
        
    def start(self, close=False):
        # Create plot window
        win = self.WIN_CLASS(toolbar=True, wintitle=self.name)
        win.show()
        QApplication.processEvents()
        plot = win.get_plot()
        
        # Create item (ignore this step in benchmark result!)
        self.make_item()
        
        # Benchmarking
        t0 = time.time()
        self.add_to_plot(plot)
        print(self.name+':')
        print("    N  = %d" % self.nsamples)
        plot.replot()  # Force replot
        print("    dt = %d ms" % ((time.time()-t0)*1e3))
        if close:
            win.close()

class CurveBM(BaseBM):
    MAKE_FUNC = make.curve
    WIN_CLASS = CurveWindow
    
    def compute_data(self):
        x = np.linspace(-10, 10, self.nsamples)
        y = np.sin(np.sin(np.sin(x)))
        return x, y

class HistogramBM(CurveBM):
    MAKE_FUNC = make.histogram
    
    def compute_data(self):
        data = np.random.normal(size=self.nsamples)
        return (data, )

class ErrorBarBM(CurveBM):
    MAKE_FUNC = make.merror
    def __init__(self, name, nsamples, dx=False, **options):
        super(ErrorBarBM, self).__init__(name, nsamples, **options)
        self.dx = dx
        
    def compute_data(self):
        x, y = super(ErrorBarBM, self).compute_data()
        if not self.dx:
            return x, y, x/100.
        else:
            return x, y, x/100., x/20.

class ImageBM(BaseBM):
    MAKE_FUNC = make.image
    WIN_CLASS = ImageWindow
    
    def compute_data(self):
        data = np.zeros((self.nsamples, self.nsamples), dtype=np.float32)
        m = 10
        step = int(self.nsamples/m)
        for i in range(m):
            for j in range(m):
                data[i*step:(i+1)*step, j*step:(j+1)*step] = i*m+j
        return (data, )

class PColorBM(BaseBM):
    MAKE_FUNC = make.pcolor
    WIN_CLASS = ImageWindow
    
    def compute_data(self):
        N = self.nsamples
        r, th = np.meshgrid(np.linspace(1., 16, N), np.linspace(0., np.pi, N))
        x = r*np.cos(th)
        y = r*np.sin(th)
        z = 4*th+r
        return x, y, z


def run():
    """Run benchmark"""
    # Print informations banner
    from plotpy import qt
    import plotpy
    qt_lib = {'pyqt': 'PyQt4', 'pyqt5': 'PyQt5', 'pyside': 'PySide'}[qt.API]
    title = "plotpy plot benchmark [%s v%s (Qt v%s), plotpy v%s]" %\
            (qt_lib, qt.__version__, qt.QtCore.__version__, plotpy.__version__)
    print(title)
    print('-'*len(title))
    print()

    import plotpy
    app = plotpy.qapplication()
    
    # Run benchmarks
    close = True
    for benchmark in (
          CurveBM('Simple curve', 5e6),
          CurveBM('Curve with markers', 2e5,
                  marker="Ellipse", markersize=10),
          CurveBM('Curve with sticks', 1e6,
                  curvestyle="Sticks"),
          ErrorBarBM('Error bar curve (vertical bars only)', 1e4),
          ErrorBarBM('Error bar curve (horizontal and vertical bars)', 1e4,
                     dx=True),
          HistogramBM('Simple histogram', 1e6, bins=1e5),
          PColorBM('Polar pcolor', 1e3),
          ImageBM('Simple image', 7e3, interpolation='antialiasing'),
                     ):
        benchmark.start(close=close)
    if not close:
        app.exec_()


if __name__ == "__main__":
    run()
