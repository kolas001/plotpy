# -*- coding: utf-8 -*-
#
# Copyright © 2009-2010 CEA
# Pierre Raybaut
# Licensed under the terms of the CECILL License
# (see guiqwt/__init__.py for details)

"""
EnhancedQwtPlot
---------------
An enhanced QwtPlot class that provides methods
for handling plotitems and axes better
"""

import sys
import numpy as np

from PyQt4.QtGui import QSizePolicy, QColor, QPixmap, QPrinter
from PyQt4.QtCore import QSize, Qt
from PyQt4.Qwt5 import (QwtPlot, QwtLinearScaleEngine, QwtLog10ScaleEngine,
                        QwtText, QwtPlotCanvas)

from guidata.configtools import get_font

# Local imports
from guiqwt.config import CONF, _
from guiqwt.events import StatefulEventFilter
from guiqwt.interfaces import IBasePlotItem, IItemType, ISerializableType
from guiqwt.styles import ItemParameters, AxeStyleParam, AxesParam
from guiqwt.signals import (SIG_ITEMS_CHANGED, SIG_ACTIVE_ITEM_CHANGED,
                            SIG_ITEM_SELECTION_CHANGED, SIG_ITEM_MOVED,
                            SIG_PLOT_LABELS_CHANGED)

PARAMETERS_TITLE_ICON = {
                         'grid': (_("Grid..."), "grid.png" ),
                         'axes': (_("Axes style..."), "axes.png" ),
                         'item': (_("Parameters..."),"settings.png" ),
                         }
    

class EnhancedQwtPlot(QwtPlot):
    """
    An enhanced QwtPlot class that provides
    methods for handling plotitems and axes better
    
    It distinguishes activatable items from basic QwtPlotItems.
    
    Activatable items must support IBasePlotItem interface and should
    be added to the plot using add_item methods.
    
    Signals:
    SIG_ITEMS_CHANGED, SIG_ACTIVE_ITEM_CHANGED
    """
    # Gestion des axes
    AXES = {
            'bottom': QwtPlot.xBottom,
            'left': QwtPlot.yLeft,
            'top': QwtPlot.xTop,
            'right': QwtPlot.yRight,
            }
    
    AXIS_TYPES = {"lin" : QwtLinearScaleEngine,
                  "log" : QwtLog10ScaleEngine }

    AXIS_CONF_OPTIONS = ("axis", "axis", "axis", "axis")

    def __init__(self, parent=None, section="plot"):
        super(EnhancedQwtPlot, self).__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.manager = None
        self.filter = StatefulEventFilter(self)
        self.items = []
        self.active_item = None
        self.last_selected = {} # a mapping from item type to last selected item
        self.axes_styles = [AxeStyleParam(_(u"Left")),
                            AxeStyleParam(_(u"Right")),
                            AxeStyleParam(_(u"Bottom")),
                            AxeStyleParam(_(u"Top"))]
        self._active_xaxis = QwtPlot.xBottom
        self._active_yaxis = QwtPlot.yLeft
        self.read_axes_styles(section, self.AXIS_CONF_OPTIONS)
        self.font_title = get_font(CONF, section, "title")
        canvas = self.canvas()
        canvas.setFocusPolicy(Qt.StrongFocus)
        canvas.setFocusIndicator(QwtPlotCanvas.ItemFocusIndicator)
        self.connect(self, SIG_ITEM_MOVED, self._move_selected_items_together)
        
    def _move_selected_items_together(self, item, x0, y0, x1, y1):
        """Selected items move together"""
        for selitem in self.get_selected_items():
            if selitem is not item and selitem.can_move():
                selitem.move_with_selection(x1-x0, y1-y0)

    def set_manager(self, manager):
        self.manager = manager

    def sizeHint(self):
        """Preferred size"""
        return QSize(400, 300)
        
    def get_title(self):
        return unicode(self.title().text())

    def set_title(self, title):
        text = QwtText(title)
        text.setFont(self.font_title)
        self.setTitle(text)
        self.emit(SIG_PLOT_LABELS_CHANGED, self)

    def read_axes_styles(self, section, options):
        """Read axes styles from section and options (one option
        for each axis in the order left,right,bottom,top).
        skip axis if option is None
        """
        for prm, option in zip(self.axes_styles, options):
            if option is None:
                continue
            prm.read_config(CONF, section, option)
        self.update_all_axes_styles()
        
    def get_axis_title(self, axis_id):
        """Get axis title"""
        return self.axes_styles[axis_id].title
        
    def set_axis_title(self, axis_id, text):
        """Set axis title"""
        self.axes_styles[axis_id].title = text
        self.update_axis_style(axis_id)
        self.emit(SIG_PLOT_LABELS_CHANGED, self)
    
    def set_axis_font(self, axis_id, font):
        """Set axis font"""
        self.axes_styles[axis_id].title_font.update_param(font)
        self.axes_styles[axis_id].ticks_font.update_param(font)
        self.update_axis_style(axis_id)
    
    def set_axis_color(self, axis_id, color):
        """
        Set axis color
        color: color name (string) or QColor instance
        """
        if isinstance(color, basestring):
            color = QColor(color)
        self.axes_styles[axis_id].color = str(color.name())
        self.update_axis_style(axis_id)

    def update_axis_style(self, axis_id):
        """Update axis style"""
        style = self.axes_styles[axis_id]
        
        title_font = style.title_font.build_font()
        ticks_font = style.ticks_font.build_font()
        self.setAxisFont(axis_id, ticks_font)
        
        axis_text = self.axisTitle(axis_id)
        axis_text.setFont(title_font)
        axis_text.setText(style.title)
        axis_text.setColor(QColor(style.color))
        self.setAxisTitle(axis_id, axis_text)

    def update_all_axes_styles(self):
        for axis_id in self.AXES.itervalues():
            self.update_axis_style(axis_id)

    def get_items(self, z_sorted=False, item_type=None):
        """Return widget item list
        (items are based on IBasePlotItem's interface)"""
        if z_sorted:
            items = sorted(self.items, reverse=True, key=lambda x:x.z())
        else:
            items = self.items
        if item_type is None:
            return items
        else:
            assert issubclass(item_type, IItemType)
            return [item for item in items if item_type in item.types()]
            
    def save_widget(self, fname):
        """Grab widget's window and save it to filename (*.png, *.pdf)"""
        fname = unicode(fname)
        if fname.lower().endswith('.pdf'):
            printer = QPrinter()
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOrientation(QPrinter.Landscape)
            printer.setOutputFileName(fname)
            printer.setCreator('guidata')
            self.print_(printer)
        elif fname.lower().endswith('.png'):
            pixmap = QPixmap.grabWidget(self)
            pixmap.save(fname, 'PNG')
        else:
            raise RuntimeError(_("Unknown file extension"))
        
    def get_selected_items(self, item_type=None):
        """Return selected items"""
        if item_type is None:
            return [item for item in self.items if item.selected]
        else:
            assert issubclass(item_type, IItemType)
            return [item for item in self.items
                    if item.selected and item_type in item.types()]
            
        
    def get_max_z(self):
        """
        Return maximum z-order for all items registered in plot
        If there is no item, return 0
        """
        if self.items:
            return max([_it.z() for _it in self.items])
        else:
            return 0
        
    def add_item(self, item, z=None):
        """
        Add a *plot item* instance to this *plot widget*
        
        item: QwtPlotItem (PyQt4.Qwt5) object implementing
              the IBasePlotItem interface (guiqwt.interfaces)
        """
        assert hasattr(item, "__implements__")
        assert IBasePlotItem in item.__implements__
        item.attach(self)
        if z is not None:
            item.setZ(z)
        else:
            item.setZ(self.get_max_z()+1)
        self.items.append(item)
        self.emit(SIG_ITEMS_CHANGED, self)
        
    def add_item_with_z_offset(self, item, zoffset):
        """
        Add a plot *item* instance within a specified z range, over *zmin*
        """
        zlist = sorted([_it.z() for _it in self.items
                        if _it.z() >= zoffset]+[zoffset-1])
        dzlist = np.argwhere(np.diff(zlist) > 1)
        if len(dzlist) == 0:
            z = max(zlist)+1
        else:
            z = zlist[dzlist]+1
        self.add_item(item, z=z)
        
    def del_item(self, item):
        """
        Remove item from widget
        Convenience function (see 'del_items')
        """
        try:
            self.del_items([item])
        except ValueError:
            raise ValueError, "item not in plot"

    def del_items(self, items):
        """Remove item from widget"""
        items = items[:] # copy the list to avoid side effects when we empty it
        active_item = self.get_active_item()
        while items:
            item = items.pop()
            item.detach()
            # raises ValueError if item not in list
            self.items.remove(item)
            self.__clean_item_references(item)
        self.emit(SIG_ITEMS_CHANGED, self)
        if active_item is not self.get_active_item():
            self.emit(SIG_ACTIVE_ITEM_CHANGED, self)

    def save_items(self, iofile, selected=False):
        if selected:
            items = self.get_selected_items()
        else:
            items = self.items[:]
        items = [item for item in items if ISerializableType in item.types()]
        import pickle
        pickle.dump(items, iofile)

    def restore_items(self, iofile):
        import pickle
        items = pickle.load(iofile)
        for item in items:
            self.add_item(item, z=item.z())

    def __clean_item_references(self, item):
        """Remove all reference to this item (active,
        last_selected"""
        if item is self.active_item:
            self.active_item = None
        for key, it in self.last_selected.items():
            if item is it:
                del self.last_selected[key]

    def set_items(self, *args):
        """Utility function used to quickly setup a plot
        with a set of items"""
        self.del_all_items()
        for item in args:
            self.add_item(item)

    def del_all_items(self):
        """Remove (detach) all attached items"""
        self.del_items(self.items)
        
    def __swap_items_z(self, item1, item2):
        old_item1_z, old_item2_z = item1.z(), item2.z()
        item1.setZ(max([_it.z() for _it in self.items])+1)
        item2.setZ(old_item1_z)
        item1.setZ(old_item2_z)
        
    def move_up(self, item_list):
        """Move item(s) up, i.e. to the foreground
        (swap item with the next item in z-order)
        
        item: plot item *or* list of plot items
        
        Return True if items have been moved effectively"""
        objects = self.get_items(z_sorted=True)
        items = sorted(list(item_list), reverse=True,
                       key=lambda x:objects.index(x))
        changed = False
        if objects.index(items[-1]) > 0:
            for item in items:
                index = objects.index(item)
                self.__swap_items_z(item, objects[index-1])
                changed = True
        if changed:
            self.emit(SIG_ITEMS_CHANGED, self)
        return changed
    
    def move_down(self, item_list):
        """Move item(s) down, i.e. to the background
        (swap item with the previous item in z-order)
        
        item: plot item *or* list of plot items
        
        Return True if items have been moved effectively"""
        objects = self.get_items(z_sorted=True)
        items = sorted(list(item_list), reverse=False,
                       key=lambda x:objects.index(x))
        changed = False
        if objects.index(items[-1]) < len(objects)-1:
            for item in items:
                index = objects.index(item)
                self.__swap_items_z(item, objects[index+1])
                changed = True
        if changed:
            self.emit(SIG_ITEMS_CHANGED, self)
        return changed

    def set_items_readonly(self, state):
        """Set all items readonly state to *state*
        Default item's readonly state: True (items can't be deleted)"""
        for item in self.get_items():
            item.set_readonly(state)
        self.emit(SIG_ITEMS_CHANGED, self)

    def select_item(self, item):
        item.select()
        for itype in item.types():
            self.last_selected[itype] = item
        self.emit(SIG_ITEM_SELECTION_CHANGED, self)

    def unselect_item(self, item):
        item.unselect()
        self.emit(SIG_ITEM_SELECTION_CHANGED, self)

    def get_last_active_item(self, item_type):
        assert issubclass(item_type, IItemType)
        return self.last_selected.get(item_type)

    def select_all(self):
        """Select all selectable items"""
        last_item = None
        block = self.blockSignals(True)
        for item in self.items:
            if item.can_select():
                self.select_item(item)
                last_item = item
        self.blockSignals(block)
        self.emit(SIG_ITEM_SELECTION_CHANGED, self)
        self.set_active_item(last_item)

    def unselect_all(self):
        """Unselect all selected items"""
        for item in self.items:
            if item.can_select():
                item.unselect()
        self.set_active_item(None)
        self.emit(SIG_ITEM_SELECTION_CHANGED, self)

    def select_some_items(self, items):
        active = self.active_item
        block = self.blockSignals(True)
        self.unselect_all()
        if items:
            new_active_item = items[-1]
        else:
            new_active_item = None
        for item in items:
            self.select_item(item)
            if active is item:
                new_active_item = item
        self.set_active_item(new_active_item)
        self.blockSignals(block)
        if new_active_item is not active:
            # if the new selection doesn't include the
            # previously active item
            self.emit(SIG_ACTIVE_ITEM_CHANGED, self)
        self.emit(SIG_ITEM_SELECTION_CHANGED, self)
        
    def set_active_item(self, item):
        """Set active item, and unselect the old active item"""
        self.active_item = item
        if self.active_item is not None:
            if not item.selected:
                self.select_item(self.active_item)
            self._active_xaxis = item.xAxis()
            self._active_yaxis = item.yAxis()
        self.emit(SIG_ACTIVE_ITEM_CHANGED, self)

    def get_active_axes(self):
        item = self.active_item
        if item is not None:
            self._active_xaxis = item.xAxis()
            self._active_yaxis = item.yAxis()
        return self._active_xaxis, self._active_yaxis

    def get_active_item(self, force=False):
        """
        Return active item
        Force item activation if there is no active item
        """
        if force and not self.active_item:
            for item in self.get_items():
                if item.can_select():
                    self.set_active_item(item)
                    break
        return self.active_item

    def get_nearest_object(self, pos, close_dist=0):
        """
        Return nearest item from position 'pos'
        If close_dist > 0: return the first found item (higher z) which
                           distance to 'pos' is less than close_dist
        else: return the closest item
        """
        selobj, distance, inside, handle = None, sys.maxint, None, None
        for obj in self.get_items(z_sorted=True):
            if not obj.isVisible() or not obj.can_select():
                continue
            d, _handle, _inside, other = obj.hit_test(pos)
            if d < distance:
                selobj, distance, handle, inside = obj, d, _handle, _inside
                if d < close_dist:
                    break
            if other is not None:
                # e.g. LegendBoxItem: selecting a curve ('other') instead of 
                #                     legend box ('obj')
                return other, 0, None, True
        return selobj, distance, handle, inside

    def get_nearest_object_in_z(self, pos):
        """
        Return nearest item for which position 'pos' is inside of it
        (iterate over items with respect to their 'z' coordinate)
        """
        selobj, distance, inside, handle = None, sys.maxint, None, None
        for obj in self.get_items(z_sorted=True):
            if not obj.isVisible() or not obj.can_select():
                continue
            d, _handle, _inside, _other = obj.hit_test(pos)
            if _inside:
                selobj, distance, handle, inside = obj, d, _handle, _inside
                break
        return selobj, distance, handle, inside

    def get_axis_scale(self, axis):
        """Return the name ('lin' or 'log') of the scale used by axis"""
        engine = self.axisScaleEngine(axis)
        for axis_label, axis_type in self.AXIS_TYPES.items():
            if isinstance(engine, axis_type):
                return axis_label
        return "lin"  # unknown default to linear

    def set_axis_scale(self, axis, scale):
        """Set axis scale
        Example: self.set_axis_scale(curve.yAxis(), 'lin')"""
        self.setAxisScaleEngine(axis, self.AXIS_TYPES[scale]())

    def set_scales(self, xscale, yscale):
        """Set active curve scales
        Example: self.set_scales('lin', 'lin')"""
        ax, ay = self.get_active_axes()
        self.set_axis_scale(ax, xscale)
        self.set_axis_scale(ay, yscale)
        self.replot()

    def enable_used_axes(self):
        """
        Enable only used axes
        For now, this is needed only by the pyplot interface
        """
        for axis in self.AXES.itervalues():
            self.enableAxis(axis, True)
        self.disable_unused_axes()

    def disable_unused_axes(self):
        """Disable unused axes"""
        used_axes = set()
        for item in self.get_items():
            used_axes.add(item.xAxis())
            used_axes.add(item.yAxis())
        unused_axes = set(self.AXES.itervalues()) - set(used_axes)
        for axis in unused_axes:
            self.enableAxis(axis, False)
        
    def get_context_menu(self):
        """Return widget context menu"""
        return self.manager.get_context_menu(self)

    def get_plot_parameters_status(self, key):
        if key == "item":
            return self.get_active_item() is not None
        else:
            return True

    def get_selected_item_parameters(self, itemparams):
        for item in self.get_selected_items():
            item.get_item_parameters(itemparams)
        # Retrieving active_item's parameters after every other item:
        # this way, the common datasets will be based on its parameters
        active_item = self.get_active_item()
        active_item.get_item_parameters(itemparams)
    
    def get_axesparam_class(self, item):
        """Return AxesParam dataset class associated to item's type"""
        return AxesParam
    
    def get_plot_parameters(self, key, itemparams):
        """
        Return a list of DataSets for a given parameter key
        the datasets will be edited and passed back to set_plot_parameters
        
        this is a generic interface to help building context menus
        using the BasePlotMenuTool
        """
        if key == "axes":
            for i, axeparam in enumerate(self.axes_styles):
                itemparams.add("AxeStyleParam%d" % i, self, axeparam)
        elif key == "item":
            active_item = self.get_active_item()
            if not active_item:
                return
            self.get_selected_item_parameters(itemparams)
            Param = self.get_axesparam_class(active_item)
            axesparam = Param(title=_("Axes"), icon='lin_lin.png',
                              comment=_("Axes associated to selected item"))
            axesparam.update_param(active_item)
            itemparams.add("AxesParam", self, axesparam)
            
    def set_item_parameters(self, itemparams):
        """Set item (plot, here) parameters"""
        # Axe styles
        datasets = [itemparams.get("AxeStyleParam%d" % i) for i in range(4)]
        if datasets[0] is not None:
            self.axes_styles = datasets
            self.update_all_axes_styles()
        # Changing active item's associated axes
        dataset = itemparams.get("AxesParam")
        if dataset is not None:
            active_item = self.get_active_item()
            dataset.update_axes(active_item)

    def edit_plot_parameters(self, key):
        """
        Edit plot parameters
        """
        multiselection = len(self.get_selected_items()) > 1
        itemparams = ItemParameters(multiselection=multiselection)
        self.get_plot_parameters(key, itemparams)
        title, icon = PARAMETERS_TITLE_ICON[key]
        itemparams.edit(self, title, icon)
        
    def do_autoscale(self, replot=True):
        """Do autoscale on all axes"""
        for axis_id in self.AXES.itervalues():
            self.setAxisAutoScale(axis_id)
        if replot:
            self.replot()

    def disable_autoscale(self):
        """Re-apply the axis scales so as to disable autoscaling
        without changing the view"""
        for axis_id in self.AXES.itervalues():
            axis = self.axisScaleDiv(axis_id)
            lb = axis.lowerBound()
            hb = axis.upperBound()
            self.setAxisScale(axis_id, lb, hb)

    def invalidate(self):
        """Invalidate paint cache and schedule redraw
        use instead of replot when only the content
        of the canvas needs redrawing (axes, shouldn't change)
        """
        self.canvas().invalidatePaintCache()
        self.update()

## Keep this around to debug too many replots
##    def replot(self):
##        import traceback
##        traceback.print_stack()
##        QwtPlot.replot(self)