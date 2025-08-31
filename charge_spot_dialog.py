import os
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, Qt, QTimer, pyqtSlot
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                                QLabel, QLineEdit, QPushButton, QSpinBox, QListWidget, 
                                QListWidgetItem, QTabWidget, QWidget, QComboBox,
                                QCheckBox, QProgressBar, QTextEdit, QGroupBox,
                                QMessageBox, QFileDialog, QTableWidget, QTableWidgetItem,
                                QHeaderView, QAbstractItemView, QSlider)
from qgis.PyQt.QtGui import QIcon, QPixmap, QFont
from qgis.core import (QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY, 
                      QgsField, QgsProject, QgsSymbol, QgsRendererCategory,
                      QgsCategorizedSymbolRenderer, QgsMarkerSymbol, 
                      QgsSvgMarkerSymbolLayer, QgsSimpleMarkerSymbolLayer,
                      QgsMessageLog, Qgis, QgsCoordinateReferenceSystem)
from qgis.PyQt.QtCore import QVariant
import json
from datetime import datetime
try:
    from .pdf_export import PDFExporter
    PDF_EXPORT_AVAILABLE = True
except ImportError:
    PDF_EXPORT_AVAILABLE = False


class ChargeSpotDialog(QDialog):
    """Dialog for ChargeSpot plugin."""
    
    map_click_requested = pyqtSignal()
    search_completed = pyqtSignal(list)
    radius_changed = pyqtSignal(float)  # Signal for search radius changes
    
    def __init__(self, iface, api_client):
        super(ChargeSpotDialog, self).__init__()
        self.iface = iface
        self.api_client = api_client
        self.current_stations = []
        self.filtered_stations = []
        self.api_worker = None
        if PDF_EXPORT_AVAILABLE:
            self.pdf_exporter = PDFExporter()
        else:
            self.pdf_exporter = None
        
        self.setupUi()
        self.connect_signals()
        
    def setupUi(self):
        """Setup the user interface."""
        self.setWindowTitle("ChargeSpot - Electric Vehicle Charging Stations")
        self.setMinimumSize(800, 600)
        
        # Main layout
        main_layout = QVBoxLayout()
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Search tab
        search_tab = self._create_search_tab()
        self.tab_widget.addTab(search_tab, "Search")
        
        # Results tab
        results_tab = self._create_results_tab()
        self.tab_widget.addTab(results_tab, "Results")
        
        # Settings tab
        settings_tab = self._create_settings_tab()
        self.tab_widget.addTab(settings_tab, "Settings")
        
        main_layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        self.setLayout(main_layout)
    
    def _create_search_tab(self):
        """Create the search tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # API Configuration Group
        api_group = QGroupBox("API Configuration")
        api_layout = QGridLayout()
        
        api_layout.addWidget(QLabel("API Key (Recommended):"), 0, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Enter OpenChargeMap API key (get free key at openchargemap.org)")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_edit, 0, 1)
        
        self.show_api_key_btn = QPushButton("Show/Hide")
        self.show_api_key_btn.clicked.connect(self.toggle_api_key_visibility)
        api_layout.addWidget(self.show_api_key_btn, 0, 2)
        
        # API key help
        api_help_label = QLabel(
            '<small><i>Note: API key may be required to avoid rate limits. '
            'Get a free key at <a href="https://openchargemap.org/site/develop">openchargemap.org/site/develop</a></i></small>'
        )
        api_help_label.setOpenExternalLinks(True)
        api_help_label.setWordWrap(True)
        api_layout.addWidget(api_help_label, 1, 0, 1, 3)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Search Parameters Group
        search_group = QGroupBox("Search Parameters")
        search_layout = QGridLayout()
        
        # Center point selection
        search_layout.addWidget(QLabel("Center Point:"), 0, 0)
        self.center_display = QLineEdit()
        self.center_display.setReadOnly(True)
        self.center_display.setPlaceholderText("Click 'Select on Map' to choose center point")
        search_layout.addWidget(self.center_display, 0, 1)
        
        self.select_center_btn = QPushButton("Select on Map")
        self.select_center_btn.clicked.connect(self.request_map_click)
        search_layout.addWidget(self.select_center_btn, 0, 2)
        
        # Radius info label
        self.radius_info = QLabel("Click on map to select center point and adjust search radius")
        self.radius_info.setStyleSheet("color: #666666; font-style: italic;")
        search_layout.addWidget(self.radius_info, 1, 0, 1, 3)  # Span all columns
        
        # Max results
        search_layout.addWidget(QLabel("Max Results:"), 2, 0)
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(10, 1000)
        self.max_results_spin.setValue(200)
        search_layout.addWidget(self.max_results_spin, 2, 1)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Search button
        self.search_btn = QPushButton("Search Charging Stations")
        self.search_btn.setMinimumHeight(40)
        self.search_btn.setEnabled(False)  # Disabled until center point is set
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.search_btn.setFont(font)
        layout.addWidget(self.search_btn)
        
        # Add stretch to push everything to top
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def _create_results_tab(self):
        """Create the results tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Filter and sort controls
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Filter by:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All", "Access Type", "Operator", "Status", 
            "Connection Type", "Power Level"
        ])
        filter_layout.addWidget(self.filter_combo)
        
        self.filter_value_combo = QComboBox()
        filter_layout.addWidget(self.filter_value_combo)
        
        filter_layout.addWidget(QLabel("Sort by:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Distance", "Name", "Operator", "Status", "Number of Points"
        ])
        filter_layout.addWidget(self.sort_combo)
        
        self.sort_desc_check = QCheckBox("Descending")
        filter_layout.addWidget(self.sort_desc_check)
        
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "Name", "Distance (km)", "Address", "Operator", 
            "Status", "Access Type", "Connections", "Actions"
        ])
        
        # Configure table
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.results_table)
        
        # Export controls
        export_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        export_layout.addWidget(self.select_all_btn)
        
        self.clear_selection_btn = QPushButton("Clear Selection")
        export_layout.addWidget(self.clear_selection_btn)
        
        export_layout.addStretch()
        
        self.export_pdf_btn = QPushButton("Export Selected to PDF")
        self.export_pdf_btn.setEnabled(False)
        export_layout.addWidget(self.export_pdf_btn)
        
        layout.addLayout(export_layout)
        
        widget.setLayout(layout)
        return widget
    
    def _create_settings_tab(self):
        """Create the settings tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Layer settings
        layer_group = QGroupBox("Layer Settings")
        layer_layout = QGridLayout()
        
        layer_layout.addWidget(QLabel("Layer Name:"), 0, 0)
        self.layer_name_edit = QLineEdit("Charging Stations")
        layer_layout.addWidget(self.layer_name_edit, 0, 1)
        
        layer_layout.addWidget(QLabel("Remove existing layers:"), 1, 0)
        self.remove_existing_check = QCheckBox()
        self.remove_existing_check.setChecked(True)
        layer_layout.addWidget(self.remove_existing_check, 1, 1)
        
        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)
        
        # About section
        about_group = QGroupBox("About")
        about_layout = QVBoxLayout()
        
        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setMaximumHeight(150)
        about_text.setPlainText(
            "ChargeSpot QGIS Plugin v1.0\n\n"
            "This plugin helps you find and visualize electric vehicle charging stations "
            "using the OpenChargeMap API. Features include:\n\n"
            "• Interactive map-based search\n"
            "• Detailed station information\n"
            "• Filtering and sorting capabilities\n"
            "• PDF export functionality\n"
            "• Custom visualization with icons\n\n"
            "Data provided by OpenChargeMap.org"
        )
        about_layout.addWidget(about_text)
        
        about_group.setLayout(about_layout)
        layout.addWidget(about_group)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def connect_signals(self):
        """Connect UI signals to handlers."""
        self.search_btn.clicked.connect(self.search_charging_stations)
        self.filter_combo.currentTextChanged.connect(self.update_filter_values)
        self.filter_value_combo.currentTextChanged.connect(self.apply_filters)
        self.sort_combo.currentTextChanged.connect(self.apply_filters)
        self.sort_desc_check.toggled.connect(self.apply_filters)
        self.select_all_btn.clicked.connect(self.select_all_results)
        self.clear_selection_btn.clicked.connect(self.clear_result_selection)
        self.export_pdf_btn.clicked.connect(self.export_to_pdf)
        self.results_table.itemSelectionChanged.connect(self.update_export_button)
        

        
    def get_center_point(self):
        """Get the current center point coordinates."""
        if hasattr(self, 'center_x') and hasattr(self, 'center_y'):
            return self.center_x, self.center_y
        return None
    
    def toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        if self.api_key_edit.echoMode() == QLineEdit.Password:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
    
    def request_map_click(self):
        """Request map click for center point selection."""
        self.setWindowState(self.windowState() | Qt.WindowMinimized)  # Minimize instead of hide
        self.map_click_requested.emit()
        
        # Show message to user
        QMessageBox.information(
            self.iface.mainWindow(),  # Use main window as parent
            "Select Center Point",
            "Click on the map to select the center point for your search.\n\n"
            "The dialog will reappear automatically after you click.\n\n"
            "Note: You can click anywhere on the map, with or without a base map loaded."
        )
    
    def set_center_point(self, x, y, show_confirmation=True):
        """Set the center point from map click."""
        self.center_x = x
        self.center_y = y
        self.center_display.setText(f"Longitude: {x:.6f}, Latitude: {y:.6f}")
        self.search_btn.setEnabled(True)
        
        # Restore window and bring to front
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()
        
        # Show confirmation message only if requested
        if show_confirmation:
            QMessageBox.information(
                self,
                "Center Point Set",
                f"Center point successfully set to:\n"
                f"Longitude: {x:.6f}\n"
                f"Latitude: {y:.6f}\n\n"
                f"You can now configure the search radius and click 'Search Charging Stations'."
            )
    
    def search_charging_stations(self, radius_km=None):
        """Search for charging stations."""
        if not hasattr(self, 'center_x') or not hasattr(self, 'center_y'):
            QMessageBox.warning(
                self,
                "Missing Center Point",
                "Please select a center point on the map first."
            )
            return
        
        # Start search
        self.search_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText("Searching for charging stations...")
        
        # Get API key
        api_key = self.api_key_edit.text().strip() if self.api_key_edit.text().strip() else None
        
        # Use provided radius or default to 10 km
        search_radius = radius_km if radius_km is not None else 10
        
        # Start async API call
        self.api_worker = self.api_client.get_async(
            self.center_y,  # latitude
            self.center_x,  # longitude
            search_radius,
            api_key
        )
        
        self.api_worker.finished.connect(self.handle_api_response)
        self.api_worker.error.connect(self.handle_api_error)
        self.api_worker.start()
    
    def handle_api_response(self, stations):
        """Handle successful API response."""
        self.search_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if not stations:
            self.status_label.setText("No charging stations found")
            QMessageBox.information(
                self,
                "No Results",
                "No charging stations data found in the selected area.\n\nTry increasing the search radius or selecting a different location."
            )
            return
            
        self.status_label.setText(f"Found {len(stations)} charging stations")
        
        self.current_stations = stations
        self.filtered_stations = stations.copy()
        
        # Update results table
        self.populate_results_table()
        
        # Update filter options
        self.update_all_filter_values()
        
        # Switch to results tab
        self.tab_widget.setCurrentIndex(1)
        
        # Emit signal for map layer creation
        self.search_completed.emit(stations)
    
    def handle_api_error(self, error_message):
        """Handle API error."""
        self.search_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Search failed")
        
        QMessageBox.critical(
            self,
            "API Error",
            f"Failed to fetch charging stations:\n\n{error_message}"
        )
    
    def populate_results_table(self):
        """Populate the results table with filtered stations."""
        self.results_table.setRowCount(len(self.filtered_stations))
        
        for row, station in enumerate(self.filtered_stations):
            # Name
            self.results_table.setItem(row, 0, QTableWidgetItem(station.get('name', 'Unknown')))
            
            # Distance
            distance = station.get('distance')
            distance_text = f"{distance:.2f}" if distance is not None else "N/A"
            self.results_table.setItem(row, 1, QTableWidgetItem(distance_text))
            
            # Address
            self.results_table.setItem(row, 2, QTableWidgetItem(station.get('address', 'Unknown')))
            
            # Operator
            self.results_table.setItem(row, 3, QTableWidgetItem(station.get('operator', 'Unknown')))
            
            # Status
            self.results_table.setItem(row, 4, QTableWidgetItem(station.get('status', 'Unknown')))
            
            # Access Type
            self.results_table.setItem(row, 5, QTableWidgetItem(station.get('access_type', 'Unknown')))
            
            # Connections
            conn_types = station.get('connection_types', [])
            conn_text = ', '.join(conn_types[:3])  # Show first 3 types
            if len(conn_types) > 3:
                conn_text += "..."
            self.results_table.setItem(row, 6, QTableWidgetItem(conn_text))
            
            # Actions - Info button
            info_btn = QPushButton("Info")
            info_btn.clicked.connect(lambda checked, s=station: self.show_station_info(s))
            self.results_table.setCellWidget(row, 7, info_btn)
    
    def show_station_info(self, station):
        """Show detailed station information."""
        info_dialog = StationInfoDialog(station, self)
        info_dialog.exec_()
    
    def update_filter_values(self):
        """Update filter value combo based on selected filter type."""
        filter_type = self.filter_combo.currentText()
        self.filter_value_combo.clear()
        
        if filter_type == "All" or not self.current_stations:
            return
        
        # Get unique values for the selected filter type
        values = set()
        for station in self.current_stations:
            if filter_type == "Access Type":
                values.add(station.get('access_type', 'Unknown'))
            elif filter_type == "Operator":
                values.add(station.get('operator', 'Unknown'))
            elif filter_type == "Status":
                values.add(station.get('status', 'Unknown'))
            elif filter_type == "Connection Type":
                values.update(station.get('connection_types', []))
            elif filter_type == "Power Level":
                values.update(station.get('power_levels', []))
        
        self.filter_value_combo.addItems(sorted(values))
    
    def update_all_filter_values(self):
        """Update all filter values when new data is loaded."""
        current_filter = self.filter_combo.currentText()
        self.update_filter_values()
    
    def apply_filters(self):
        """Apply current filters and sorting to the results."""
        if not self.current_stations:
            return
        
        # Apply filter
        filter_type = self.filter_combo.currentText()
        filter_value = self.filter_value_combo.currentText()
        
        if filter_type == "All" or not filter_value:
            self.filtered_stations = self.current_stations.copy()
        else:
            self.filtered_stations = []
            for station in self.current_stations:
                if self._station_matches_filter(station, filter_type, filter_value):
                    self.filtered_stations.append(station)
        
        # Apply sorting
        sort_by = self.sort_combo.currentText()
        reverse = self.sort_desc_check.isChecked()
        
        if sort_by == "Distance":
            self.filtered_stations.sort(
                key=lambda s: s.get('distance', float('inf')), 
                reverse=reverse
            )
        elif sort_by == "Name":
            self.filtered_stations.sort(
                key=lambda s: s.get('name', '').lower(), 
                reverse=reverse
            )
        elif sort_by == "Operator":
            self.filtered_stations.sort(
                key=lambda s: s.get('operator', '').lower(), 
                reverse=reverse
            )
        elif sort_by == "Status":
            self.filtered_stations.sort(
                key=lambda s: s.get('status', '').lower(), 
                reverse=reverse
            )
        elif sort_by == "Number of Points":
            self.filtered_stations.sort(
                key=lambda s: s.get('num_points', 0), 
                reverse=reverse
            )
        
        # Update table
        self.populate_results_table()
        
        # Update status
        self.status_label.setText(
            f"Showing {len(self.filtered_stations)} of {len(self.current_stations)} stations"
        )
    
    def _station_matches_filter(self, station, filter_type, filter_value):
        """Check if station matches the current filter."""
        if filter_type == "Access Type":
            return station.get('access_type', 'Unknown') == filter_value
        elif filter_type == "Operator":
            return station.get('operator', 'Unknown') == filter_value
        elif filter_type == "Status":
            return station.get('status', 'Unknown') == filter_value
        elif filter_type == "Connection Type":
            return filter_value in station.get('connection_types', [])
        elif filter_type == "Power Level":
            return filter_value in station.get('power_levels', [])
        return True
    
    def select_all_results(self):
        """Select all results in the table."""
        self.results_table.selectAll()
    
    def clear_result_selection(self):
        """Clear selection in results table."""
        self.results_table.clearSelection()
    
    def update_export_button(self):
        """Update export button state based on selection."""
        has_selection = len(self.results_table.selectedItems()) > 0
        self.export_pdf_btn.setEnabled(has_selection)
    
    def export_to_pdf(self):
        """Export selected stations to PDF."""
        if not PDF_EXPORT_AVAILABLE or self.pdf_exporter is None:
            QMessageBox.warning(
                self, 
                "PDF Export Unavailable", 
                "PDF export functionality is not available.\n"
                "Please install the required dependency:\n"
                "pip install reportlab"
            )
            return
            
        selected_rows = set()
        for item in self.results_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select stations to export.")
            return
        
        # Get selected stations
        selected_stations = [self.filtered_stations[row] for row in sorted(selected_rows)]
        
        # Choose file location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Charging Stations to PDF",
            f"charging_stations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF Files (*.pdf)"
        )
        
        if file_path:
            try:
                self.pdf_exporter.export_stations(selected_stations, file_path)
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Successfully exported {len(selected_stations)} stations to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Export Failed",
                    f"Failed to export PDF:\n{str(e)}"
                )
    
    def create_charging_stations_layer(self, stations):
        """Create a vector layer with charging stations."""
        if not stations:
            return None
        
        # Remove existing layer if requested
        layer_name = self.layer_name_edit.text() or "Charging Stations"
        if self.remove_existing_check.isChecked():
            layers = QgsProject.instance().mapLayersByName(layer_name)
            for layer in layers:
                QgsProject.instance().removeMapLayer(layer.id())
        
        # Get the project CRS
        project_crs = QgsProject.instance().crs()
        
        # Create vector layer using project CRS
        layer = QgsVectorLayer(f'Point?crs={project_crs.authid()}', layer_name, 'memory')
        provider = layer.dataProvider()
        
        # Add fields
        fields = [
            QgsField('id', QVariant.Int),
            QgsField('name', QVariant.String),
            QgsField('address', QVariant.String),
            QgsField('operator', QVariant.String),
            QgsField('status', QVariant.String),
            QgsField('access_type', QVariant.String),
            QgsField('distance', QVariant.Double),
            QgsField('num_points', QVariant.Int),
            QgsField('connection_types', QVariant.String),
            QgsField('power_levels', QVariant.String),
            QgsField('phone', QVariant.String),
            QgsField('url', QVariant.String),
        ]
        provider.addAttributes(fields)
        layer.updateFields()
        
        # Set up coordinate transformation from WGS84 to project CRS
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        if project_crs != wgs84_crs:
            from qgis.core import QgsCoordinateTransform
            transform = QgsCoordinateTransform(wgs84_crs, project_crs, QgsProject.instance())
        else:
            transform = None
        
        # Add features
        features = []
        for station in stations:
            feature = QgsFeature()
            
            # Create point in WGS84
            wgs84_point = QgsPointXY(station['longitude'], station['latitude'])
            
            # Transform to project CRS if needed
            if transform:
                try:
                    transformed_point = transform.transform(wgs84_point)
                    feature.setGeometry(QgsGeometry.fromPointXY(transformed_point))
                except Exception as e:
                    # Fallback: use original coordinates
                    feature.setGeometry(QgsGeometry.fromPointXY(wgs84_point))
            else:
                feature.setGeometry(QgsGeometry.fromPointXY(wgs84_point))
            
            feature.setAttributes([
                station.get('id'),
                station.get('name', 'Unknown'),
                station.get('address', 'Unknown'),
                station.get('operator', 'Unknown'),
                station.get('status', 'Unknown'),
                station.get('access_type', 'Unknown'),
                station.get('distance'),
                station.get('num_points', 0),
                ', '.join(station.get('connection_types', [])),
                ', '.join(station.get('power_levels', [])),
                station.get('phone', ''),
                station.get('url', ''),
            ])
            
            features.append(feature)
        
        provider.addFeatures(features)
        layer.updateExtents()
        
        # Apply symbology
        self._apply_layer_symbology(layer)
        
        return layer
    
    def _apply_layer_symbology(self, layer):
        """Apply custom symbology to the charging stations layer."""
        # Create categories based on status
        categories = []
        
        # Define colors and icons for different statuses
        status_styles = {
            'Operational': {'color': 'green', 'icon': 'circle'},
            'Available': {'color': 'green', 'icon': 'circle'},
            'Out of Service': {'color': 'red', 'icon': 'cross'},
            'Unknown': {'color': 'orange', 'icon': 'circle'},
            'Planned': {'color': 'blue', 'icon': 'triangle'},
        }
        
        for status, style in status_styles.items():
            symbol = QgsMarkerSymbol.createSimple({
                'name': style['icon'],
                'color': style['color'],
                'size': '8',
                'outline_color': 'black',
                'outline_width': '0.5'
            })
            
            category = QgsRendererCategory(status, symbol, status)
            categories.append(category)
        
        # Default category for other statuses
        default_symbol = QgsMarkerSymbol.createSimple({
            'name': 'circle',
            'color': 'gray',
            'size': '8',
            'outline_color': 'black',
            'outline_width': '0.5'
        })
        default_category = QgsRendererCategory('', default_symbol, 'Other')
        categories.append(default_category)
        
        # Apply renderer
        renderer = QgsCategorizedSymbolRenderer('status', categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()


class StationInfoDialog(QDialog):
    """Dialog to show detailed station information."""
    
    def __init__(self, station, parent=None):
        super().__init__(parent)
        self.station = station
        self.setupUi()
    
    def setupUi(self):
        """Setup the station info dialog UI."""
        self.setWindowTitle(f"Station Info - {self.station.get('name', 'Unknown')}")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        # Basic information
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        
        info_content = self._build_info_content()
        info_text.setHtml(info_content)
        
        layout.addWidget(info_text)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
    
    def _build_info_content(self):
        """Build HTML content for station information."""
        station = self.station
        
        html = f"""
        <h2>{station.get('name', 'Unknown Station')}</h2>
        
        <h3>Location</h3>
        <p><strong>Address:</strong> {station.get('address', 'Unknown')}</p>
        <p><strong>Coordinates:</strong> {station.get('latitude', 'N/A')}, {station.get('longitude', 'N/A')}</p>
        <p><strong>Distance:</strong> {station.get('distance', 'N/A')} km</p>
        
        <h3>General Information</h3>
        <p><strong>Operator:</strong> {station.get('operator', 'Unknown')}</p>
        <p><strong>Status:</strong> {station.get('status', 'Unknown')}</p>
        <p><strong>Access Type:</strong> {station.get('access_type', 'Unknown')}</p>
        <p><strong>Number of Charging Points:</strong> {station.get('num_points', 0)}</p>
        
        <h3>Connection Information</h3>
        <p><strong>Connection Types:</strong> {', '.join(station.get('connection_types', ['Unknown']))}</p>
        <p><strong>Power Levels:</strong> {', '.join(station.get('power_levels', ['Unknown']))}</p>
        
        <h3>Contact Information</h3>
        <p><strong>Phone:</strong> {station.get('phone', 'Not available')}</p>
        <p><strong>Email:</strong> {station.get('email', 'Not available')}</p>
        <p><strong>Website:</strong> {station.get('url', 'Not available')}</p>
        
        <h3>Additional Information</h3>
        <p><strong>Cost:</strong> {station.get('cost', 'Unknown')}</p>
        <p><strong>Comments:</strong> {station.get('comments', 'None')}</p>
        <p><strong>Date Created:</strong> {station.get('date_created', 'Unknown')}</p>
        <p><strong>Last Verified:</strong> {station.get('date_last_verified', 'Unknown')}</p>
        """
        
        # Add detailed connection information if available
        connections = station.get('connections', [])
        if connections:
            html += "<h3>Detailed Connection Information</h3>"
            for i, conn in enumerate(connections, 1):
                html += f"""
                <h4>Connection {i}</h4>
                <ul>
                <li><strong>Type:</strong> {conn.get('type', 'Unknown')}</li>
                <li><strong>Level:</strong> {conn.get('level', 'Unknown')}</li>
                <li><strong>Power:</strong> {conn.get('power_kw', 'Unknown')} kW</li>
                <li><strong>Current Type:</strong> {conn.get('current_type', 'Unknown')}</li>
                <li><strong>Quantity:</strong> {conn.get('quantity', 1)}</li>
                <li><strong>Status:</strong> {conn.get('status', 'Unknown')}</li>
                </ul>
                """
        
        return html

