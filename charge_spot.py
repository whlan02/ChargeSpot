# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ChargeSpot
                                 A QGIS plugin
 QGIS Plugin to find and visualize electric vehicle charging stations
                              -------------------
        begin                : 2024-12-20
        copyright            : (C) 2024 by ChargeSpot
        email                : contact@chargespot.com
 ***************************************************************************/
"""

import os.path
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import QgsProject, QgsMapLayer, QgsWkbTypes, QgsMessageLog, Qgis
from qgis.gui import QgsMapToolEmitPoint
# import resources  # Not needed for this plugin

from .charge_spot_dialog import ChargeSpotDialog
from .api_client import OpenChargeMapAPI


class ChargeSpot:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'ChargeSpot_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&ChargeSpot')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        
        # Initialize the dialog and API client
        self.dlg = None
        self.api_client = OpenChargeMapAPI()
        self.map_tool = None
        self.current_layer = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('ChargeSpot', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = os.path.join(os.path.dirname(__file__), 'icon.svg')
        self.add_action(
            icon_path,
            text=self.tr(u'Find Charging Stations'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr(u'&ChargeSpot'),
                action)
            self.iface.removeToolBarIcon(action)

    def setup_map_tool(self):
        """Setup the map tool for selecting center points."""
        if self.map_tool is None:
            self.map_tool = QgsMapToolEmitPoint(self.iface.mapCanvas())
            self.map_tool.canvasClicked.connect(self.map_clicked)

    def map_clicked(self, point, button):
        """Handle map click events to set center point."""
        if self.dlg:
            # Transform coordinates to WGS84 if needed
            source_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject
            
            # Transform to WGS84 (EPSG:4326) for the API
            dest_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
            
            try:
                transformed_point = transform.transform(point)
                final_x, final_y = transformed_point.x(), transformed_point.y()
                self.dlg.set_center_point(final_x, final_y)
            except Exception as e:
                # Fallback: assume coordinates are already in WGS84
                self.dlg.set_center_point(point.x(), point.y())
            
            # Deactivate map tool and show dialog again
            self.iface.mapCanvas().unsetMapTool(self.map_tool)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = ChargeSpotDialog(self.iface, self.api_client)
            self.dlg.map_click_requested.connect(self.activate_map_tool)
            self.dlg.search_completed.connect(self.handle_search_results)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        
        # Deactivate map tool when dialog closes
        if self.map_tool:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)

    def activate_map_tool(self):
        """Activate the map tool for point selection."""
        self.setup_map_tool()
        self.iface.mapCanvas().setMapTool(self.map_tool)

    def handle_search_results(self, charging_stations):
        """Handle the search results and create a layer."""
        if charging_stations:
            layer = self.dlg.create_charging_stations_layer(charging_stations)
            if layer:
                QgsProject.instance().addMapLayer(layer)
                self.current_layer = layer
                # Zoom to layer extent
                self.iface.mapCanvas().setExtent(layer.extent())
                self.iface.mapCanvas().refresh()
                
                QMessageBox.information(
                    self.dlg,
                    "Success",
                    f"Found and added {len(charging_stations)} charging stations to the map!"
                )
        else:
            QMessageBox.warning(
                self.dlg,
                "No Results",
                "No charging stations found in the specified area."
            )

