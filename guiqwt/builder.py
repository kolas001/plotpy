# -*- coding: utf-8 -*-
#
# Copyright © 2009-2010 CEA
# Pierre Raybaut <pierre.raybaut@cea.fr>
# Licensed under the terms of the CECILL License
# (see guiqwt/__init__.py for details)

"""
A builder singleton class used to simplify the creation of plot items
"""

from numpy import arange, array, zeros, meshgrid

from PyQt4.Qwt5 import QwtPlot

# Local imports
from guiqwt.config import _, CONF, make_title
from guiqwt.curve import CurveItem, GridItem
from guiqwt.histogram import HistogramItem
from guiqwt.errorbar import ErrorBarCurveItem
from guiqwt.image import (ImageItem, QuadGridItem, TrImageItem, XYImageItem,
                          Histogram2DItem)
from guiqwt.shapes import (XRangeSelection, RectangleShape, EllipseShape,
                           SegmentShape)
from guiqwt.annotations import (AnnotatedRectangle, AnnotatedEllipse,
                                AnnotatedSegment)
from guiqwt.styles import (update_style_attr, CurveParam, ErrorBarParam,
                           style_generator, LabelParam, LegendParam, ImageParam,
                           TrImageParam, HistogramParam, Histogram2DParam,
                           ImageFilterParam, MARKERS, COLORS, GridParam,
                           LineStyleParam, AnnotationParam)
from guiqwt.label import (LabelItem, LegendBoxItem, RangeComputation,
                          RangeComputation2d, DataInfoLabel,
                          SelectedLegendBoxItem)
from guiqwt.io import imagefile_to_array
import os.path as osp

# default offset positions for anchors
ANCHOR_OFFSETS = {
                  "TL" : ( 5,  5),
                  "TR" : (-5,  5),
                  "BL" : ( 5, -5),
                  "BR" : (-5, -5),
                  "L"  : ( 5,  0),
                  "R"  : (-5,  0),
                  "T"  : ( 0,  5),
                  "B"  : ( 0, -5),
                  }

CURVE_COUNT = 0
HISTOGRAM_COUNT = 0
IMAGE_COUNT = 0
LABEL_COUNT = 0
HISTOGRAM2D_COUNT = 0

class PlotItemBuilder(object):
    """
    This is just a bare class used to regroup
    a set of factory functions in a single object
    """
    AXES = {
            'bottom': QwtPlot.xBottom,
            'left'  : QwtPlot.yLeft,
            'top'   : QwtPlot.xTop,
            'right' : QwtPlot.yRight,
            }
    
    def __init__(self):
        self.style = style_generator()
        
    def gridparam(self, background=None,
                  major_enabled=None, minor_enabled=None,
                  major_style=None, minor_style=None):
        """
        Make guiqwt.styles.GridParam instance:
           background = canvas background color
           major_enabled = tuple (major_xenabled, major_yenabled)
           minor_enabled = tuple (minor_xenabled, minor_yenabled)
           major_style = tuple (major_xstyle, major_ystyle)
           minor_style = tuple (minor_xstyle, minor_ystyle)
           
        Style: tuple (style, color, width)
        """
        gridparam = GridParam(title=_("Grid"), icon="lin_lin.png")
        gridparam.read_config(CONF, "plot", "grid")
        if background is not None:
            gridparam.background = background
        if major_enabled is not None:
            gridparam.maj_xenabled, gridparam.maj_yenabled = major_enabled
        if minor_enabled is not None:
            gridparam.min_xenabled, gridparam.min_yenabled = minor_enabled
        if major_style is not None:
            style = LineStyleParam()
            linestyle, color, style.width = major_style
            style.set_style_from_matlab(linestyle)
            style.color = COLORS.get(color, color) # MATLAB-style
        if minor_style is not None:
            style = LineStyleParam()
            linestyle, color, style.width = minor_style
            style.set_style_from_matlab(linestyle)
            style.color = COLORS.get(color, color) # MATLAB-style
        return gridparam
    
    def grid(self, background=None, major_enabled=None, minor_enabled=None,
             major_style=None, minor_style=None):
        """
        Make QwtPlotGrid instance:
           background = canvas background color
           major_enabled = tuple (major_xenabled, major_yenabled)
           minor_enabled = tuple (minor_xenabled, minor_yenabled)
           major_style = tuple (major_xstyle, major_ystyle)
           minor_style = tuple (minor_xstyle, minor_ystyle)
           
        Style: tuple (style, color, width)
        """
        gridparam = self.gridparam(background, major_enabled, minor_enabled,
                                   major_style, minor_style)
        return GridItem(gridparam)
    
    def __set_axes(self, curve, xaxis, yaxis):
        """Set curve axes"""
        for axis in (xaxis, yaxis):
            if axis not in self.AXES:
                raise RuntimeError("Unknown axis %s" % axis)
        curve.setXAxis(self.AXES[xaxis])
        curve.setYAxis(self.AXES[yaxis])

    def __set_param(self, param, title, color, linestyle, linewidth,
                    marker, markersize, markerfacecolor, markeredgecolor,
                    shade, fitted):
        """Apply parameters to a CurveParam instance"""
        if title:
            param.label = title
        if color is not None:
            color = COLORS.get(color, color) # MATLAB-style
            param.line.color = color
        if linestyle is not None:
            param.line.set_style_from_matlab(linestyle)
        if linewidth is not None:
            param.line.width = linewidth
        if marker is not None:
            if marker in MARKERS:
                param.symbol.update_param(MARKERS[marker]) # MATLAB-style
            else:
                param.symbol.marker = marker
        if markersize is not None:
            param.symbol.size = markersize
        if markerfacecolor is not None:
            markerfacecolor = COLORS.get(markerfacecolor,
                                         markerfacecolor) # MATLAB-style
            param.symbol.facecolor = markerfacecolor
        if markeredgecolor is not None:
            markeredgecolor = COLORS.get(markeredgecolor,
                                         markeredgecolor) # MATLAB-style
            param.symbol.edgecolor = markeredgecolor
        if shade is not None:
            param.shade = shade
        if fitted is not None:
            param.fitted = fitted

    def __get_arg_triple_plot(self, args):
        """Convert MATLAB-like arguments into x, y, style"""
        if len(args)==1:
            if isinstance(args[0], basestring):
                x = array((), float)
                y = array((), float)
                style = args[0]
            else:
                y = args[0]
                x = arange(len(y))
                style = self.style.next()
        elif len(args)==2:
            a1, a2 = args
            if isinstance(a2, basestring):
                y = a1
                x = arange(len(y))
                style = a2
            else:
                x = a1
                y = a2
                style = self.style.next()
        elif len(args)==3:
            x, y, style = args
        else:
            raise TypeError("Wrong number of arguments")
        return x, y, style
        
    def __get_arg_triple_errorbar(self, args):
        """Convert MATLAB-like arguments into x, y, style"""
        if len(args)==2:
            y, dy = args
            x = arange(len(y))
            dx = zeros(len(y))
            style = self.style.next()
        elif len(args)==3:
            a1, a2, a3 = args
            if isinstance(a3, basestring):
                y, dy = a1, a2
                x = arange(len(y))
                dx = zeros(len(y))
                style = a3
            else:
                x, y, dy = args
                dx = zeros(len(y))
                style = self.style.next()
        elif len(args)==4:
            a1, a2, a3, a4 = args
            if isinstance(a4, basestring):
                x, y, dy = a1, a2, a3
                dx = zeros(len(y))
                style = a4
            else:
                x, y, dx, dy = args
                style = self.style.next()
        elif len(args)==5:
            x, y, dx, dy, style = args
        else:
            raise TypeError("Wrong number of arguments")
        return x, y, dx, dy, style
    
    def mcurve(self, *args, **kwargs):
        """
        Make curve based on MATLAB-like syntax
        
        Example: mcurve(x, y, 'r+')
        """
        x, y, style = self.__get_arg_triple_plot(args)
        basename = _("Curve")
        param = CurveParam(title=basename, icon='curve.png')
        if "label" in kwargs:
            param.label = kwargs.pop("label")
        else:
            global CURVE_COUNT
            CURVE_COUNT += 1
            param.label = make_title(basename, CURVE_COUNT)
        update_style_attr(style, param)
        return self.pcurve(x, y, param, **kwargs)
    
    def pcurve(self, x, y, param, xaxis="bottom", yaxis="left"):
        """
        Make curve based on a CurveParam instance
        
        Usage: pcurve(x, y, param)
        """
        curve = CurveItem(param)
        curve.set_data(x, y)
        curve.update_params()
        self.__set_axes(curve, xaxis, yaxis)
        return curve

    def curve(self, x, y, title=u"",
              color=None, linestyle=None, linewidth=None,
              marker=None, markersize=None, markerfacecolor=None,
              markeredgecolor=None, shade=None, fitted=None,
              xaxis="bottom", yaxis="left"):
        """
        Make curve from x,y data
        
        Examples:
        curve(x, y, marker='Ellipse', markerfacecolor='#ffffff')
        which is equivalent to (MATLAB-style support):
        curve(x, y, marker='o', markerfacecolor='w')
        """
        basename = _("Curve")
        param = CurveParam(title=basename, icon='curve.png')
        if not title:
            global CURVE_COUNT
            CURVE_COUNT += 1
            title = make_title(basename, CURVE_COUNT)
        self.__set_param(param, title, color, linestyle, linewidth, marker,
                         markersize, markerfacecolor, markeredgecolor,
                         shade, fitted)
        return self.pcurve(x, y, param, xaxis, yaxis)

    def merror(self, *args, **kwargs):
        """
        Make curve based on MATLAB-like syntax
        
        Example: mcurve(x, y, 'r+')
        """
        x, y, dx, dy, style = self.__get_arg_triple_errorbar(args)
        basename = _("Curve")
        curveparam = CurveParam(title=basename, icon='curve.png')
        errorbarparam = ErrorBarParam(title=_("Error bars"),
                                      icon='errorbar.png')
        if "label" in kwargs:
            curveparam.label = kwargs["label"]
        else:
            global CURVE_COUNT
            CURVE_COUNT += 1
            curveparam.label = make_title(basename, CURVE_COUNT)
        update_style_attr(style, curveparam)
        errorbarparam.color = curveparam.line.color
        return self.perror(x, y, dx, dy, curveparam, errorbarparam)

    def perror(self, x, y, dx, dy, curveparam, errorbarparam,
               xaxis="bottom", yaxis="left"):
        """
        Make errorbar curve based on a ErrorBarParam instance
        
        Usage: perror(x, y, dx, dy, curveparam, errorbarparam)
        """
        curve = ErrorBarCurveItem(curveparam, errorbarparam)
        curve.set_data(x, y, dx, dy)
        curve.update_params()
        self.__set_axes(curve, xaxis, yaxis)
        return curve
        
    def error(self, x, y, dx, dy, title=u"",
              color=None, linestyle=None, linewidth=None, marker=None,
              markersize=None, markerfacecolor=None, markeredgecolor=None,
              shade=None, fitted=None, xaxis="bottom", yaxis="left"):
        """
        Make errorbar curve from x,y,dx,dy data
        
        Examples:
        error(x, y, None, dy, marker='Ellipse', markerfacecolor='#ffffff')
        which is equivalent to (MATLAB-style support):
        error(x, y, None, dy, marker='o', markerfacecolor='w')
        """
        basename = _("Curve")
        curveparam = CurveParam(title=basename, icon='curve.png')
        errorbarparam = ErrorBarParam(title=_("Error bars"),
                                      icon='errorbar.png')
        if not title:
            global CURVE_COUNT
            CURVE_COUNT += 1
            curveparam.label = make_title(basename, CURVE_COUNT)
        self.__set_param(curveparam, title, color, linestyle, linewidth, marker,
                         markersize, markerfacecolor, markeredgecolor,
                         shade, fitted)
        errorbarparam.color = curveparam.line.color
        return self.perror(x, y, dx, dy, curveparam, errorbarparam,
                           xaxis, yaxis)
    
    def histogram(self, data, bins=None, logscale=None, remove_first_bin=None,
                  title=u"", color=None, xaxis="bottom", yaxis="left"):
        """
        1-D Histogram
        
        Parameters:
        data (1-D array)
        bins: number of bins (int)
        logscale: Y-axis scale (bool)
        """
        basename = _("Histogram")
        histparam = HistogramParam(title=basename, icon='histogram.png')
        curveparam = CurveParam()
        curveparam.read_config(CONF, "histogram", "curve")
        if not title:
            global HISTOGRAM_COUNT
            HISTOGRAM_COUNT += 1
            title = make_title(basename, HISTOGRAM_COUNT)
        curveparam.label = title
        if color is not None:
            curveparam.line.color = color
        if bins is not None:
            histparam.n_bins = bins
        if logscale is not None:
            histparam.logscale = logscale
        if remove_first_bin is not None:
            histparam.remove_first_bin = remove_first_bin
        return self.phistogram(data, curveparam, histparam, xaxis, yaxis)
        
    def phistogram(self, data, curveparam, histparam,
                   xaxis="bottom", yaxis="left"):
        """
        Make histogram based on a CurveParam and HistogramParam instances
        
        Usage: phistogram(data, curveparam, histparam)
        """
        hist = HistogramItem(curveparam, histparam)
        hist.update_params()
        hist.set_hist_data(data)
        self.__set_axes(hist, xaxis, yaxis)
        return hist

    def __set_image_param(self, param, title, background_color,
                          alpha_mask, alpha, colormap, **kwargs):
        if title:
            param.label = title
        else:
            global IMAGE_COUNT
            IMAGE_COUNT += 1
            param.label = make_title(_("Image"), IMAGE_COUNT)
        if background_color is not None:
            param.background = background_color
        if alpha_mask is not None:
            param.alpha_mask = alpha_mask
        if alpha is not None:
            param.alpha = alpha
        if colormap is not None:
            param.colormap = colormap
        for key, val in kwargs.items():
            setattr(param, key, val)

    def _get_image_data(self, data, filename, title, cmap):
        if data is None:
            assert filename is not None
            data = imagefile_to_array(filename)
        if title is None and filename is not None:
            title = osp.basename(filename)
        return data, filename, title, cmap

    def image(self, data=None, filename=None, title=None, background_color=None,
              alpha_mask=None, alpha=None, colormap=None,
              xaxis="bottom", yaxis="left", zaxis="right"):
        """
        Make image from data
        """
        param = ImageParam(title=_("Image"), icon='image.png')
        params = self._get_image_data(data, filename, title, colormap)
        data, filename, title, colormap = params
        self.__set_image_param(param, title, background_color,
                               alpha_mask, alpha, colormap)
        image = ImageItem(data, param)
        image.set_filename(filename)
        return image
        
    def quadgrid(self, X, Y, Z, filename=None, title=None,
                 background_color=None, alpha_mask=None, alpha=None,
                 colormap=None, xaxis="bottom", yaxis="left", zaxis="right"):
        """
        Make a pseudocolor plot item of a 2-D array
        """
        param = ImageParam(title=_("Image"), icon='image.png')
        self.__set_image_param(param, title, background_color,
                               alpha_mask, alpha, colormap)
        image = QuadGridItem(X, Y, Z, param)
        return image

    def pcolor(self, *args, **kwargs):
        """
        Make a pseudocolor plot item of a 2-D array based on MATLAB-like syntax
        
        Examples:
            pcolor(C)
            pcolor(X, Y, C)
        """
        if len(args) == 1:
            Z, = args
            M, N = Z.shape
            X, Y = meshgrid(arange(N, dtype=Z.dtype), arange(M, dtype=Z.dtype))
        elif len(args) == 3:
            X, Y, Z = args
        else:
            raise RuntimeError("1 or 3 non-keyword arguments expected")
        return self.quadgrid(X, Y, Z, **kwargs)

    def trimage(self, data=None, filename=None, title=None,
                background_color=None, alpha_mask=None, alpha=None,
                colormap=None, xaxis="bottom", yaxis="left", zaxis="right",
                x0=0.0, y0=0.0, angle=0.0, dx=1.0, dy=1.0,
                interpolation='linear'):
        """
        Make image from data
        
        Parameters:
        data: image pixel data
        filename: image filename (if data is not specified)
        title: image title (optional)
        x0, y0: position
        angle: angle (radians)
        dx, dy: pixel size along X and Y axes
        interpolation: 'nearest', 'linear' (default), 'antialiasing' (5x5)
        """
        param = TrImageParam(title=_("Image"), icon='image.png')
        params = self._get_image_data(data, filename, title, colormap)
        data, filename, title, colormap = params
        self.__set_image_param(param, title, background_color,
                               alpha_mask, alpha, colormap,
                               x0=x0, y0=y0, angle=angle, dx=dx, dy=dy)
        interp_methods = {'nearest': 0, 'linear': 1, 'antialiasing': 5}
        param.interpolation = interp_methods[interpolation]
        image = TrImageItem(data, param)
        image.set_filename(filename)
        return image

    def xyimage(self, x, y, data, title=None, background_color=None,
                alpha_mask=None, alpha=None, colormap=None,
                xaxis="bottom", yaxis="left", zaxis="right"):
        """
        Make xyimage from data
        """
        param = ImageParam(title=_("Image"), icon='image.png')
        self.__set_image_param(param, title, background_color,
                               alpha_mask, alpha, colormap)
        return XYImageItem(x, y, data, param)
    
    def imagefilter(self, xmin, xmax, ymin, ymax,
                    imageitem, filter, title=None):
        """
        Rectangular area image filter
        
        Parameters:
        xmin, xmax, ymin, ymax: filter area bounds
        imageitem: An imageitem instance
        filter: function (x, y, data) --> data
        """
        param = ImageFilterParam(_("Filter"), icon="funct.png")
        param.xmin, param.xmax, param.ymin, param.ymax = xmin, xmax, ymin, ymax
        if title is not None:
            param.label = title
        filt = imageitem.get_filter(filter, param)
        _m, _M = imageitem.get_lut_range()
        filt.set_lut_range([_m, _M])
        return filt
    
    def histogram2D(self, X, Y, NX=None, NY=None, logscale=None,
                    title=None, transparent=None):
        """
        2-D Histogram
        
        Parameters:
        X: data (1-D array)
        Y: data (1-D array)
        NX: Number of bins along x-axis (int)
        NY: Number of bins along y-axis (int)
        logscale: Z-axis scale (bool)
        title: item title (string)
        transparent: enable transparency (bool)
        """
        basename = _("2-D Histogram")
        param = Histogram2DParam(title=basename, icon='histogram2d.png')
        if NX is not None:
            param.nx_bins = NX
        if NY is not None:
            param.ny_bins = NY
        if logscale is not None:
            param.logscale = int(logscale)
        if title is not None:
            param.label = title
        else:
            global HISTOGRAM2D_COUNT
            HISTOGRAM2D_COUNT += 1
            param.label = make_title(basename, HISTOGRAM2D_COUNT)
        if transparent is not None:
            param.transparent = transparent
        return Histogram2DItem(X, Y, param)

    def label(self, text, g, c, anchor, title=""):
        """
        Make label
        
        Arguments:
        text: label text (string)
        g: position in plot coordinates (tuple) or relative position (string)
        c: position in canvas coordinates (tuple)
        anchor: anchor position in relative position (string)
        title: label name (optional)
        
        Examples:
        make.label("Relative position", (x[0], y[0]), (10, 10), "BR")
        make.label("Absolute position", "R", (0,0), "R")
        """
        basename = _("Label")
        param = LabelParam(basename, icon='label.png')
        param.read_config(CONF, "plot", "label")
        if title:
            param.label = title
        else:
            global LABEL_COUNT
            LABEL_COUNT += 1
            param.label = make_title(basename, LABEL_COUNT)
        if isinstance(g, tuple):
            param.abspos = False
            param.xg, param.yg = g
        else:
            param.abspos = True
            param.absg = g
        if c is None:
            c = ANCHOR_OFFSETS[anchor]
        param.xc, param.yc = c
        param.anchor = anchor
        return LabelItem(text, param)

    def legend(self, anchor='TR', c=None, restrict_items=None):
        """
        Make legend
        
        anchor: legend position in relative position (string)
        c (optional): position in canvas coordinates (tuple)
        restrict_items (optional):
            None: all items are shown in legend box
            []: no item shown
            [item1, item2]: item1, item2 are shown in legend box
        """
        param = LegendParam(_("Legend"), icon='legend.png')
        param.read_config(CONF, "plot", "legend")
        param.abspos = True
        param.absg = anchor
        param.anchor = anchor
        if c is None:
            c = ANCHOR_OFFSETS[anchor]
        param.xc, param.yc = c
        if restrict_items is None:
            return LegendBoxItem(param)
        else:
            return SelectedLegendBoxItem(param, restrict_items)

    def range(self, xmin, xmax):
        return XRangeSelection(xmin, xmax)
        
    def __shape(self, shapeclass, x0, y0, x1, y1, title=None):
        shape = shapeclass(x0, y0, x1, y1)
        shape.set_style("plot", "shape/drag")
        if title is not None:
            shape.setTitle(title)
        return shape

    def rectangle(self, x0, y0, x1, y1, title=None):
        """
        Make rectangle shape
        x0, y0, x1, y1: rectangle coordinates
        """
        return self.__shape(RectangleShape, x0, y0, x1, y1, title)

    def ellipse(self, x0, y0, x1, y1, ratio, title=None):
        """
        Make ellipse shape
        x0, y0, x1, y1: ellipse x-axis coordinates
        ratio: ratio between y-axis and x-axis lengths
        """
        shape = EllipseShape(x0, y0, x1, y1, ratio)
        shape.set_style("plot", "shape/drag")
        if title is not None:
            shape.setTitle(title)
        return shape
        
    def circle(self, x0, y0, x1, y1, title=None):
        """
        Make circle shape
        x0, y0, x1, y1: circle diameter coordinates
        """
        return self.ellipse(x0, y0, x1, y1, 1., title=title)

    def segment(self, x0, y0, x1, y1, title=None):
        """
        Make segment shape
        x0, y0, x1, y1: segment coordinates
        """
        return self.__shape(SegmentShape, x0, y0, x1, y1, title)
        
    def __get_annotationparam(self, title, subtitle):
        param = AnnotationParam(_("Annotation"), icon="annotation.png")
        if title is not None:
            param.title = title
        if subtitle is not None:
            param.subtitle = subtitle
        return param
        
    def __annotated_shape(self, shapeclass, x0, y0, x1, y1, title, subtitle):
        param = self.__get_annotationparam(title, subtitle)
        shape = shapeclass(x0, y0, x1, y1, param)
        shape.set_style("plot", "shape/drag")
        return shape
        
    def annotated_rectangle(self, x0, y0, x1, y1, title=None, subtitle=None):
        """
        Make annotated rectangle
        
        x0, y0, x1, y1: rectangle coordinates
        title, subtitle: strings
        """
        return self.__annotated_shape(AnnotatedRectangle,
                                      x0, y0, x1, y1, title, subtitle)
        
    def annotated_ellipse(self, x0, y0, x1, y1, ratio,
                          title=None, subtitle=None):
        """
        Make annotated ellipse
        
        x0, y0, x1, y1: ellipse rectangle coordinates
        ratio: ratio between y-axis and x-axis lengths
        title, subtitle: strings
        """
        param = self.__get_annotationparam(title, subtitle)
        shape = AnnotatedEllipse(x0, y0, x1, y1, ratio, param)
        shape.set_style("plot", "shape/drag")
        return shape
                                      
    def annotated_circle(self, x0, y0, x1, y1, ratio,
                         title=None, subtitle=None):
        """
        Make annotated circle
        
        x0, y0, x1, y1: circle diameter coordinates
        title, subtitle: strings
        """
        return self.annotated_ellipse(x0, y0, x1, y1, 1., title, subtitle)
        
    def annotated_segment(self, x0, y0, x1, y1, title=None, subtitle=None):
        """
        Make annotated segment
        
        x0, y0, x1, y1: segment coordinates
        title, subtitle: strings
        """
        return self.__annotated_shape(AnnotatedSegment,
                                      x0, y0, x1, y1, title, subtitle)

    def info_label(self, anchor, comps, title=""):
        basename = _("Computation")
        param = LabelParam(basename, icon='label.png')
        param.read_config(CONF, "plot", "info_label")
        if title:
            param.label = title
        else:
            global LABEL_COUNT
            LABEL_COUNT += 1
            param.label = make_title(basename, LABEL_COUNT)
        param.abspos = True
        param.absg = anchor
        param.anchor = anchor
        c = ANCHOR_OFFSETS[anchor]
        param.xc, param.yc = c
        return DataInfoLabel(param, comps)

    def computation(self, range, anchor, label, curve, function):
        return self.computations(range, anchor, [ (curve, label, function) ])

    def computations(self, range, anchor, specs):
        comps = []
        for curve, label, function in specs:
            comp = RangeComputation(label, curve, range, function)
            comps.append(comp)
        return self.info_label(anchor, comps)

    def computation2d(self, rect, anchor, label, image, function):
        return self.computations2d(rect, anchor, [ (image, label, function) ])

    def computations2d(self, rect, anchor, specs):
        comps = []
        for image, label, function in specs:
            comp = RangeComputation2d(label, image, rect, function)
            comps.append(comp)
        return self.info_label(anchor, comps)

make = PlotItemBuilder()