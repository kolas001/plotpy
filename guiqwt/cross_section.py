# -*- coding: utf-8 -*-
#
# Copyright © 2009-2010 CEA
# Pierre Raybaut
# Licensed under the terms of the CECILL License
# (see guiqwt/__init__.py for details)

"""
Cross section related objects
"""

from PyQt4.QtCore import QSize, QPoint
from PyQt4.QtGui import QVBoxLayout, QWidget, QSizePolicy

import numpy as np

from guidata.utils import assert_interfaces_valid
from guidata.configtools import get_icon

# Local imports
from guiqwt.config import CONF, _
from guiqwt.interfaces import ICSImageItemType, IPanel, IBasePlotItem
from guiqwt.curve import CurvePlot, CurveItem
from guiqwt.image import ImagePlot
from guiqwt.styles import CurveParam, style_generator, update_style_attr
from guiqwt.tools import SelectTool, BasePlotMenuTool, AntiAliasingTool
from guiqwt.signals import (SIG_MARKER_CHANGED, SIG_PLOT_LABELS_CHANGED,
                            SIG_ANNOTATION_CHANGED, SIG_AXIS_DIRECTION_CHANGED,
                            SIG_ITEMS_CHANGED)
from guiqwt.plot import PlotManager
from guiqwt.builder import make
from guiqwt.shapes import Marker


class CrossSectionItem(CurveItem):
    """A Qwt item representing cross section data"""
    __implements__ = (IBasePlotItem,)
    _inverted = None
    
    def __init__(self, curveparam=None):
        super(CrossSectionItem, self).__init__(curveparam)

    def set_source_image(self, src):
        """
        Set source image
        (source: object with methods 'get_xsection' and 'get_ysection',
         e.g. objects derived from guiqwt.image.BaseImageItem)
        """
        self.source = src

    def get_cross_section(self, obj):
        """Get cross section data from source image"""
        raise NotImplementedError
        
    def update_plot(self, obj):
        if self.source is None:
            return
        sectx, secty = self.get_cross_section(obj)
        if self._inverted:
            self.set_data(secty, sectx)
        else:
            self.set_data(sectx, secty)
        self.update_scale()
#        plot = self.plot()
#        if plot is not None:
#            plot.do_autoscale(replot=True)

    def update_scale(self):
        raise NotImplementedError

assert_interfaces_valid(CrossSectionItem)


def get_image_data(plot, p0, p1):
    """
    Save rectangular plot area
    p0, p1: resp. top left and bottom right points (QPoint objects)
    """
    from guiqwt.image import (ImageItem, XYImageItem, TrImageItem,
                              get_image_from_plot, get_plot_source_rect)
                           
    items = [item for item in plot.items if isinstance(item, ImageItem)
             and not isinstance(item, XYImageItem)]
    if not items:
        return
    trparams = [item.get_transform() for item in items
                if isinstance(item, TrImageItem)]
    dx_max = max([dx for _x, _y, _angle, dx, _dy, _hf, _vf in trparams]+[1.])
    dy_max = max([dy for _x, _y, _angle, _dx, dy, _hf, _vf in trparams]+[1.])
    _src_x, _src_y, src_w, src_h = get_plot_source_rect(plot, p0, p1)
    return get_image_from_plot(plot, p0, p1, src_w/dx_max, src_h/dy_max)


class XCrossSectionItem(CrossSectionItem):
    """A Qwt item representing x-axis cross section data"""
    _inverted = False
    def get_cross_section(self, obj):
        """Get x-cross section data from source image"""
        if isinstance(obj, Marker):
            return self.source.get_xsection(obj.yValue())
        else:
            x0, y0, x1, y1 = obj.shape.get_rect()
            p0 = QPoint(x0, y0)
            p1 = QPoint(x1, y1)
            try:
                data = get_image_data(obj.plot(), p0, p1)
            except (ValueError, ZeroDivisionError):
                return [], []
            y = data.mean(axis=0)
            x = np.linspace(x0, x1, len(y))
            return x, y
            
    def update_scale(self):
        plot = self.plot()
        axis_id = plot.xBottom
        sdiv = self.source.plot().axisScaleDiv(axis_id)
        plot.setAxisScale(axis_id, sdiv.lowerBound(), sdiv.upperBound())
        plot.replot()

class YCrossSectionItem(CrossSectionItem):
    """A Qwt item representing y-axis cross section data"""
    _inverted = True
    def get_cross_section(self, obj):
        """Get y-cross section data from source image"""
        if isinstance(obj, Marker):
            return self.source.get_ysection(obj.xValue())
        else:
            x0, y0, x1, y1 = obj.shape.get_rect()
            p0 = QPoint(x0, y0)
            p1 = QPoint(x1, y1)
            try:
                data = get_image_data(obj.plot(), p0, p1)
            except (ValueError, ZeroDivisionError):
                return [], []
            y = data.mean(axis=1)
            x = np.linspace(y0, y1, len(y))
            return x, y
            
    def update_scale(self):
        plot = self.plot()
        axis_id = plot.yLeft
        sdiv = self.source.plot().axisScaleDiv(axis_id)
        plot.setAxisScale(axis_id, sdiv.lowerBound(), sdiv.upperBound())
        plot.replot()


class CrossSectionPlot(CurvePlot):
    """Cross section plot"""
    _height = None
    _width = None
    CS_AXIS = None
    Z_AXIS = None
    Z_MAX_MAJOR = 5
    def __init__(self, parent=None):
        super(CrossSectionPlot, self).__init__(parent=parent, title="",
                                               section="cross_section")

        self.style = style_generator()
                                               
        # a dict of dict : plot -> selected items -> CurveItem
        self._tracked_items = {}
        self._shapes = {}
        
        self.curveparam = CurveParam(_("Curve"), icon="curve.png")
        self.curveparam.read_config(CONF, "cross_section", "curve")
        
        if self._height is not None:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        if self._width is not None:
            self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
            
        self.label = make.label(_("Enable a marker"), "C", (0,0), "C")
        self.add_item(self.label)
        
        self.setAxisMaxMajor(self.Z_AXIS, self.Z_MAX_MAJOR)
        self.setAxisMaxMinor(self.Z_AXIS, 0)

    def connect_plot(self, plot):
        if not isinstance(plot, ImagePlot):
            # Connecting only to image plot widgets (allow mixing image and 
            # curve widgets for the same plot manager -- e.g. in pyplot)
            return
        self.connect(plot, SIG_ITEMS_CHANGED, self.items_changed)
        self.connect(plot, SIG_MARKER_CHANGED, self.marker_changed)
        self.connect(plot, SIG_ANNOTATION_CHANGED, self.shape_changed)
        self.connect(plot, SIG_PLOT_LABELS_CHANGED, self.plot_labels_changed)
        self.connect(plot, SIG_AXIS_DIRECTION_CHANGED, self.axis_dir_changed)
        self.plot_labels_changed(plot)
        for axis_id in plot.AXES:
            self.axis_dir_changed(plot, axis_id)
        
    def register_shape(self, plot, shape, final):
        known_shapes = self._shapes.get(plot, [])
        if shape in known_shapes:
            return
        self._shapes[plot] = known_shapes+[shape]
        param = shape.annotationparam
        param.title = "X/Y"
        param.update_annotation(shape)
        self.update_plot(shape)
        
    def unregister_shape(self, shape):
        for plot in self._shapes:
            shapes = self._shapes[plot]            
            if shape in shapes:
                shapes.pop(shapes.index(shape))
                break
        
    def standard_tools(self, manager):
        manager.add_tool(SelectTool)
        manager.add_tool(BasePlotMenuTool, "item")
        manager.add_tool(BasePlotMenuTool, "axes")
        manager.add_tool(BasePlotMenuTool, "grid")
        manager.add_tool(AntiAliasingTool)
        manager.get_default_tool().activate()
        
    def create_cross_section_item(self):
        raise NotImplementedError

    def tracked_items_gen(self):
        for plot, items in self._tracked_items.items():
            for item in items.items():
                yield item # tuple item,curve

    def __del_known_items(self, known_items, items):
        del_curves = []
        for item in known_items.keys():
            if item not in items:
                curve = known_items.pop(item)
                del_curves.append(curve)
        self.del_items(del_curves)

    def items_changed(self, plot):
        items = plot.get_items(item_type=ICSImageItemType)
        known_items = self._tracked_items.setdefault(plot, {})

        if items:
            self.__del_known_items(known_items, items)
            if len(items) == 1:
                # Removing any cached item for other plots
                for other_plot, _items in self._tracked_items.items():
                    if other_plot is not plot:
                        if not other_plot.get_items(item_type=ICSImageItemType):
                            other_known_items = self._tracked_items[other_plot]
                            self.__del_known_items(other_known_items, [])
        else:
            # if all items are deselected we keep the last known
            # selection (for one plot only)
            for other_plot, _items in self._tracked_items.items():
                if other_plot.get_items(item_type=ICSImageItemType):
                    self.__del_known_items(known_items, [])
                    break
                
        for item in items:
            if item not in known_items:
                curve = self.create_cross_section_item()
                curve.set_source_image(item)
                style = self.style.next()
                update_style_attr(style, curve.curveparam)
                curve.curveparam.update_curve(curve)
                self.add_item(curve, z=0)
                known_items[item] = curve

        nb_selected = len(list(self.tracked_items_gen()))
        if not nb_selected:
            self.replot()
            return
#        self.curveparam.shade = 1.0/nb_selected
#        for item, curve in self.tracked_items_gen():
#            self.curveparam.update_curve(curve)

    def plot_labels_changed(self, plot):
        """Plot labels have changed"""
        raise NotImplementedError
        
    def axis_dir_changed(self, plot, axis_id):
        """An axis direction has changed"""
        raise NotImplementedError
        
    def marker_changed(self, marker):
        self.update_plot(marker)

    def is_shape_known(self, shape):
        for shapes in self._shapes.values():
            if shape in shapes:
                return True
        else:
            return False
        
    def shape_changed(self, shape):
        if self.is_shape_known(shape):
            self.update_plot(shape)
        
    def update_plot(self, obj):
        if obj.plot() is None:
            self.unregister_shape(obj)
            print "unregister_shape:", repr(obj)            
            return
        if self.label.isVisible():
            self.label.hide()
        for _item, curve in self.tracked_items_gen():
            curve.update_plot(obj)


class XCrossSectionPlot(CrossSectionPlot):
    """X-axis cross section plot"""
    _height = 130
    CS_AXIS = CurvePlot.xBottom
    Z_AXIS = CurvePlot.yLeft
    def sizeHint(self):
        return QSize(self.width(), self._height)
        
    def create_cross_section_item(self):
        return XCrossSectionItem(self.curveparam)

    def plot_labels_changed(self, plot):
        """Plot labels have changed"""
        self.set_axis_title("left", plot.get_axis_title("right"))       
        self.set_axis_title("bottom", plot.get_axis_title("bottom"))
        
    def axis_dir_changed(self, plot, axis_id):
        """An axis direction has changed"""
        if axis_id == plot.xBottom:
            self.set_axis_direction("bottom", plot.get_axis_direction("bottom"))
            self.replot()
        

class YCrossSectionPlot(CrossSectionPlot):
    """Y-axis cross section plot"""
    _width = 140
    CS_AXIS = CurvePlot.yLeft
    Z_AXIS = CurvePlot.xBottom
    Z_MAX_MAJOR = 3
    def sizeHint(self):
        return QSize(self._width, self.height())
    
    def create_cross_section_item(self):
        return YCrossSectionItem(self.curveparam)

    def plot_labels_changed(self, plot):
        """Plot labels have changed"""
        self.set_axis_title("bottom", plot.get_axis_title("right"))       
        self.set_axis_title("left", plot.get_axis_title("left"))
        
    def axis_dir_changed(self, plot, axis_id):
        """An axis direction has changed"""
        if axis_id == plot.yLeft:
            self.set_axis_direction("left", plot.get_axis_direction("left"))
            self.replot()


class CrossSectionWidget(QWidget):
    """Cross section widget"""
    CrossSectionPlotKlass = None

    __implements__ = (IPanel,)

    def __init__(self, parent=None):
        super(CrossSectionWidget, self).__init__(parent)
        widget_title = _("Cross section tool")
        widget_icon = "cross_section.png"
        
        self.manager = None
        
        vlayout = QVBoxLayout()
        self.setLayout(vlayout)
        
        self.manager = PlotManager(self)
        self.cs_plot = self.CrossSectionPlotKlass(parent)
        vlayout.addWidget(self.cs_plot)
        self.manager.add_plot(self.cs_plot, "default")
        
        self.cs_plot.standard_tools(self.manager)
        self.setWindowIcon(get_icon(widget_icon))
        self.setWindowTitle(widget_title)
        
    def panel_id(self):
        raise NotImplementedError
    
    def register_panel(self, manager):
        self.manager = manager
        for plot in manager.get_plots():
            self.cs_plot.connect_plot(plot)

    def get_plot(self):
        return self.manager.get_active_plot()

    def closeEvent(self, event):
        self.hide()
        event.ignore()
        
    def register_shape(self, shape, final):
        plot = self.get_plot()
        self.cs_plot.register_shape(plot, shape, final)

assert_interfaces_valid(CrossSectionWidget)


class XCrossSectionWidget(CrossSectionWidget):
    """X-axis cross section widget"""
    CrossSectionPlotKlass = XCrossSectionPlot
    def panel_id(self):
        return "x_cross_section"

class YCrossSectionWidget(CrossSectionWidget):
    """Y-axis cross section widget"""
    CrossSectionPlotKlass = YCrossSectionPlot
    def panel_id(self):
        return "y_cross_section"