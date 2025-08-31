import os.path
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (QAction, QMessageBox, QWidget, QHBoxLayout, 
                               QVBoxLayout, QSlider, QLabel, QFrame, QPushButton,
                               QApplication)
from qgis.core import (QgsProject, QgsPointXY, QgsVectorLayer, QgsMarkerSymbol, 
                      QgsFeature, QgsGeometry, QgsCoordinateTransform, 
                      QgsCoordinateReferenceSystem, QgsFillSymbol)
from qgis.gui import QgsMapToolEmitPoint, QgsMapTool, QgsRubberBand

class RadiusMapTool(QgsMapTool):
    """Custom map tool with floating radius control."""
    
    def __init__(self, canvas, preview_callback, search_callback):
        super().__init__(canvas)
        self.canvas = canvas
        self.preview_callback = preview_callback
        self.search_callback = search_callback
        self.dragging = False
        self.center_point = None
        
        # Create floating control widget
        self.control_widget = QFrame(self.canvas)
        self.control_widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #999999;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #1f78b4;
                color: white;
                border: none;
                border-radius: 2px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #2988c4;
            }
            QPushButton:pressed {
                background-color: #166294;
            }
        """)
        self.control_widget.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        
        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(5)
        
        # Create slider layout
        slider_layout = QHBoxLayout()
        slider_layout.setContentsMargins(0, 0, 0, 0)
        
        self.radius_label = QLabel("Search Radius:")
        slider_layout.addWidget(self.radius_label)
        
        self.radius_slider = QSlider(Qt.Horizontal)
        self.radius_slider.setRange(1, 200)
        self.radius_slider.setValue(10)
        self.radius_slider.setFixedWidth(150)
        self.radius_slider.setTickPosition(QSlider.TicksBelow)
        self.radius_slider.setTickInterval(20)
        self.radius_slider.valueChanged.connect(self.on_radius_changed)
        slider_layout.addWidget(self.radius_slider)
        
        self.value_label = QLabel("10 km")
        slider_layout.addWidget(self.value_label)
        
        main_layout.addLayout(slider_layout)
        
        # Create button layout
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add stretch to push button to the right
        button_layout.addStretch()
        
        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedWidth(80)
        self.search_btn.clicked.connect(self.on_search_clicked)
        button_layout.addWidget(self.search_btn)
        
        main_layout.addLayout(button_layout)
        
        self.control_widget.setLayout(main_layout)
        self.control_widget.hide()
    
    def canvasPressEvent(self, event):
        """Handle mouse press events on the canvas."""
        if event.button() == Qt.LeftButton:
            self.center_point = self.toMapCoordinates(event.pos())
            # Call the preview callback with initial point and radius
            self.preview_callback(self.center_point, self.radius_slider.value())
            # Show control widget near the click point
            widget_pos = event.pos()
            # Position the widget 50 pixels to the right and 30 pixels above the click point
            widget_pos.setX(widget_pos.x() + 50)
            widget_pos.setY(widget_pos.y() - self.control_widget.height() - 30)
            
            # Get the global position
            global_pos = self.canvas.mapToGlobal(widget_pos)
            
            # Ensure the widget stays within the screen bounds
            screen = QApplication.primaryScreen().geometry()
            if global_pos.x() + self.control_widget.width() > screen.width():
                # If it would go off the right edge, place it to the left of the click point instead
                widget_pos.setX(event.pos().x() - self.control_widget.width() - 50)
            
            self.control_widget.move(self.canvas.mapToGlobal(widget_pos))
            self.control_widget.show()
    
    def on_radius_changed(self, value):
        """Handle radius slider value changes."""
        self.value_label.setText(f"{value} km")
        if self.center_point:
            self.preview_callback(self.center_point, value)
    
    def on_search_clicked(self):
        """Handle search button click."""
        if self.center_point:
            self.search_callback(self.center_point, self.radius_slider.value())
            self.control_widget.hide()
            # Deactivate the map tool after search
            self.canvas.unsetMapTool(self)
    
    def deactivate(self):
        """Clean up when the tool is deactivated."""
        self.control_widget.hide()
        super().deactivate()


from .charge_spot_dialog import ChargeSpotDialog
from .api_client import OpenChargeMapAPI


class ChargeSpot:

    def __init__(self, iface):
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
        self.center_point_layer = None
        self.search_area_layer = None

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
        
        # Remove the center point layer if it exists
        if self.center_point_layer:
            QgsProject.instance().removeMapLayer(self.center_point_layer.id())

    def setup_map_tool(self):
        """Setup the map tool for selecting center points."""
        if self.map_tool is None:
            self.map_tool = RadiusMapTool(
                self.iface.mapCanvas(),
                self.preview_radius_update,  # For live preview
                self.handle_radius_update    # For actual search
            )

    def create_center_point_layer(self):
        """Create a new layer for the center point if it doesn't exist."""
        if self.center_point_layer is None:
            # Get the project CRS
            project_crs = QgsProject.instance().crs()
            
            # Create a new memory layer
            self.center_point_layer = QgsVectorLayer(
                f'Point?crs={project_crs.authid()}', 
                'Search Center Point', 
                'memory'
            )
            
            # Add the layer to the project
            QgsProject.instance().addMapLayer(self.center_point_layer)
            
            # Create a distinctive symbol for the center point
            symbol = QgsMarkerSymbol.createSimple({
                'name': 'star',
                'color': '#FF0000',  # Red color
                'size': '10',
                'outline_color': '#000000',  # Black outline
                'outline_width': '1'
            })
            
            self.center_point_layer.renderer().setSymbol(symbol)
            self.center_point_layer.triggerRepaint()
            
    def create_search_area_layer(self):
        """Create a new layer for the search area if it doesn't exist."""
        if self.search_area_layer is None:
            # Get the project CRS
            project_crs = QgsProject.instance().crs()
            
            # Create a new memory layer
            self.search_area_layer = QgsVectorLayer(
                f'Polygon?crs={project_crs.authid()}', 
                'Search Area', 
                'memory'
            )
            
            # Add the layer to the project but hide it initially
            QgsProject.instance().addMapLayer(self.search_area_layer)
            
            # Create a semi-transparent blue fill symbol
            symbol = QgsFillSymbol.createSimple({
                'color': '#1f78b440',  # Semi-transparent blue
                'outline_color': '#1f78b4',  # Solid blue outline
                'outline_width': '2',
                'outline_style': 'solid'
            })
            
            self.search_area_layer.renderer().setSymbol(symbol)
            self.search_area_layer.triggerRepaint()
            
    def update_search_area(self, radius_km):
        """Update the search area circle based on center point and radius."""
        if not self.center_point_layer or self.center_point_layer.featureCount() == 0:
            return
            
        # Get the center point
        center_feature = next(self.center_point_layer.getFeatures())
        center_point = center_feature.geometry().asPoint()
        
        # Create a circle with the given radius
        # Note: We need to handle the fact that the project CRS might not be in meters
        source_crs = self.center_point_layer.crs()
        
        # Create circle in a meter-based CRS (e.g., UTM) for accurate buffering
        # We'll use UTM zone appropriate for the center point
        from math import floor
        zone = floor((center_point.x() + 180) / 6) + 1
        utm_crs = QgsCoordinateReferenceSystem(f'EPSG:{32600 + zone}')  # Northern hemisphere
        
        # Transform center point to UTM
        transform_to_utm = QgsCoordinateTransform(source_crs, utm_crs, QgsProject.instance())
        utm_center = transform_to_utm.transform(center_point)
        
        # Create circle in UTM coordinates
        radius_meters = radius_km * 1000
        # Create a point geometry
        point_geom = QgsGeometry.fromPointXY(QgsPointXY(utm_center))
        # Create circle by buffering the point
        circle = point_geom.buffer(radius_meters, 36)
        
        # Transform circle back to source CRS
        transform_from_utm = QgsCoordinateTransform(utm_crs, source_crs, QgsProject.instance())
        circle.transform(transform_from_utm)
        
        # Create or clear the search area layer
        if not self.search_area_layer:
            self.create_search_area_layer()
        else:
            # Clear all existing features
            self.search_area_layer.dataProvider().truncate()
            self.search_area_layer.updateExtents()
        
        # Add the new circle to the layer
        feature = QgsFeature()
        feature.setGeometry(circle)
        self.search_area_layer.dataProvider().addFeatures([feature])
        
        # Update layer extents and refresh
        self.search_area_layer.updateExtents()
        self.search_area_layer.triggerRepaint()
        
        # Update the map canvas
        self.iface.mapCanvas().refresh()

    def clear_center_point_layer(self):
        """Clear the center point layer."""
        if self.center_point_layer:
            self.center_point_layer.dataProvider().truncate()
            self.center_point_layer.triggerRepaint()

    def preview_radius_update(self, point, radius_km):
        """Preview the search area without starting the search."""
        # Create or clear the center point layer
        if not self.center_point_layer:
            self.create_center_point_layer()
        else:
            self.clear_center_point_layer()
        
        # Add the point to the layer
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        self.center_point_layer.dataProvider().addFeatures([feature])
        self.center_point_layer.triggerRepaint()
        
        # Update the search area preview
        self.update_search_area(radius_km)
    
    def handle_radius_update(self, point, radius_km):
        """Handle search request from the map tool."""
        # Transform coordinates to WGS84 if needed
        source_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        dest_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
        
        try:
            transformed_point = transform.transform(point)
            final_x, final_y = transformed_point.x(), transformed_point.y()
        except Exception as e:
            # Fallback: assume coordinates are already in WGS84
            final_x, final_y = point.x(), point.y()
        
        # Update dialog with new coordinates and start search
        if self.dlg:
            # Update the search area first
            self.preview_radius_update(point, radius_km)
            
            # Then start the search
            self.dlg.set_center_point(final_x, final_y)
            self.dlg.search_charging_stations(radius_km)
            
            # Deactivate the map tool after search
            self.iface.mapCanvas().unsetMapTool(self.map_tool)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog if it doesn't exist
        if not self.dlg:
            self.dlg = ChargeSpotDialog(self.iface, self.api_client)
            self.dlg.map_click_requested.connect(self.activate_map_tool)
            self.dlg.search_completed.connect(self.handle_search_results)
            self.dlg.radius_changed.connect(self.update_search_area)

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
            # Create and add the charging stations layer
            layer = self.dlg.create_charging_stations_layer(charging_stations)
            if layer:
                QgsProject.instance().addMapLayer(layer)
                self.current_layer = layer
                
                # Get the search area layer extent
                if self.search_area_layer and self.search_area_layer.featureCount() > 0:
                    # Force update the search area layer extent
                    self.search_area_layer.updateExtents()
                    
                    # Use search area extent for zooming
                    extent = self.search_area_layer.extent()
                    
                    # Debug print to check if extent is being updated
                    print(f"Search area extent: {extent.toString()}")
                    
                    # Add 20% padding
                    width = extent.width()
                    height = extent.height()
                    padding_x = width * 0.1
                    padding_y = height * 0.1
                    
                    extent.setXMinimum(extent.xMinimum() - padding_x)
                    extent.setXMaximum(extent.xMaximum() + padding_x)
                    extent.setYMinimum(extent.yMinimum() - padding_y)
                    extent.setYMaximum(extent.yMaximum() + padding_y)
                    
                    # Set the map extent and refresh
                    canvas = self.iface.mapCanvas()
                    canvas.setExtent(extent)
                    canvas.refresh()
                
                # Show success message
                project_crs = QgsProject.instance().crs()
                QMessageBox.information(
                    self.dlg,
                    "Success",
                    f"Found and added {len(charging_stations)} charging stations to the map!\n\n"
                    f"Using project CRS: {project_crs.authid()}"
                )
        else:
            QMessageBox.warning(
                self.dlg,
                "No Results",
                "No charging stations found in the specified area."
            )

