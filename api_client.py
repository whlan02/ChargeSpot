# -*- coding: utf-8 -*-
"""
OpenChargeMap API Client for ChargeSpot QGIS Plugin
"""

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

import json
from typing import List, Dict, Optional, Tuple
from qgis.PyQt.QtCore import QObject, pyqtSignal, QThread
from qgis.core import QgsMessageLog, Qgis


class APIWorker(QThread):
    """Worker thread for API calls to prevent UI blocking."""
    
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, api_client, latitude, longitude, radius, api_key=None):
        super().__init__()
        self.api_client = api_client
        self.latitude = latitude
        self.longitude = longitude
        self.radius = radius
        self.api_key = api_key
    
    def run(self):
        """Run the API call in the background thread."""
        try:
            stations = self.api_client.get_charging_stations(
                self.latitude, self.longitude, self.radius, self.api_key
            )
            self.finished.emit(stations)
        except Exception as e:
            self.error.emit(str(e))


class OpenChargeMapAPI(QObject):
    """Client for OpenChargeMap API."""
    
    BASE_URL = "https://api.openchargemap.io/v3/poi"
    
    def __init__(self):
        super().__init__()
        if not REQUESTS_AVAILABLE:
            raise ImportError("Requests library is not available. Please install it: pip install requests")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ChargeSpot-QGIS-Plugin/1.0 (Educational Use)'
        })
    
    def get_charging_stations(
        self, 
        latitude: float, 
        longitude: float, 
        radius: float = 10.0,
        api_key: Optional[str] = None,
        max_results: int = 200
    ) -> List[Dict]:
        """
        Get charging stations from OpenChargeMap API.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius: Search radius in kilometers
            api_key: Optional API key for higher rate limits
            max_results: Maximum number of results to return
            
        Returns:
            List of charging station data dictionaries
        """
        params = {
            'output': 'json',
            'latitude': latitude,
            'longitude': longitude,
            'distance': radius,
            'distanceunit': 'km',
            'maxresults': max_results
        }
        
        headers = {}
        if api_key:
            headers['X-API-Key'] = api_key
        
        try:
            QgsMessageLog.logMessage(
                f"Making API request to OpenChargeMap: lat={latitude}, lon={longitude}, radius={radius}km",
                "ChargeSpot",
                Qgis.Info
            )
            
            # Build URL for debugging
            import urllib.parse
            full_url = f"{self.BASE_URL}?" + urllib.parse.urlencode(params)
            QgsMessageLog.logMessage(f"Request URL: {full_url}", "ChargeSpot", Qgis.Info)
            
            response = self.session.get(
                self.BASE_URL,
                params=params,
                headers=headers,
                timeout=30
            )
            
            # Log response details for debugging
            QgsMessageLog.logMessage(
                f"Response status: {response.status_code}, headers: {dict(response.headers)}",
                "ChargeSpot",
                Qgis.Info
            )
            
            if response.status_code == 403:
                error_msg = (
                    f"Access forbidden (403). This could be due to:\n"
                    f"1. Rate limiting - try again later\n"
                    f"2. API key required - consider adding an API key\n"
                    f"3. Geographic restrictions\n"
                    f"Response: {response.text[:200]}"
                )
                QgsMessageLog.logMessage(error_msg, "ChargeSpot", Qgis.Critical)
                raise Exception(error_msg)
            
            response.raise_for_status()
            
            data = response.json()
            
            QgsMessageLog.logMessage(
                f"API response received: {len(data)} charging stations found",
                "ChargeSpot",
                Qgis.Info
            )
            
            return self._process_charging_stations(data)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f"\nResponse text: {e.response.text[:200]}"
            QgsMessageLog.logMessage(error_msg, "ChargeSpot", Qgis.Critical)
            raise Exception(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse API response: {str(e)}"
            QgsMessageLog.logMessage(error_msg, "ChargeSpot", Qgis.Critical)
            raise Exception(error_msg)
    
    def _process_charging_stations(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Process raw API data into a standardized format.
        
        Args:
            raw_data: Raw data from OpenChargeMap API
            
        Returns:
            List of processed charging station dictionaries
        """
        processed_stations = []
        
        for station in raw_data:
            try:
                # Extract basic information
                station_data = {
                    'id': station.get('ID'),
                    'name': self._safe_get_nested(station, ['AddressInfo', 'Title'], 'Unknown Station'),
                    'address': self._build_address(station.get('AddressInfo', {})),
                    'latitude': self._safe_get_nested(station, ['AddressInfo', 'Latitude']),
                    'longitude': self._safe_get_nested(station, ['AddressInfo', 'Longitude']),
                    'distance': station.get('AddressInfo', {}).get('Distance'),
                    'access_type': self._safe_get_nested(station, ['UsageType', 'Title'], 'Unknown'),
                    'operator': self._safe_get_nested(station, ['OperatorInfo', 'Title'], 'Unknown'),
                    'status': self._safe_get_nested(station, ['StatusType', 'Title'], 'Unknown'),
                    'verification_status': self._safe_get_nested(station, ['SubmissionStatus', 'Title'], 'Unknown'),
                    'num_points': station.get('NumberOfPoints', 0),
                    'cost': self._safe_get_nested(station, ['UsageCost'], 'Unknown'),
                    'url': station.get('URL'),
                    'phone': self._safe_get_nested(station, ['AddressInfo', 'ContactTelephone1']),
                    'email': self._safe_get_nested(station, ['AddressInfo', 'ContactEmail']),
                    'comments': station.get('GeneralComments'),
                    'date_created': station.get('DateCreated'),
                    'date_last_verified': station.get('DateLastVerified'),
                }
                
                # Extract connection information
                connections = station.get('Connections', [])
                station_data['connections'] = self._process_connections(connections)
                station_data['connection_types'] = self._get_connection_types(connections)
                station_data['power_levels'] = self._get_power_levels(connections)
                
                # Only add stations with valid coordinates
                if (station_data['latitude'] is not None and 
                    station_data['longitude'] is not None):
                    processed_stations.append(station_data)
                    
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error processing station {station.get('ID', 'unknown')}: {str(e)}",
                    "ChargeSpot",
                    Qgis.Warning
                )
                continue
        
        return processed_stations
    
    def _safe_get_nested(self, data: Dict, keys: List[str], default=None):
        """Safely get nested dictionary values."""
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current if current is not None else default
    
    def _build_address(self, address_info: Dict) -> str:
        """Build a formatted address string."""
        parts = []
        
        if address_info.get('AddressLine1'):
            parts.append(address_info['AddressLine1'])
        if address_info.get('Town'):
            parts.append(address_info['Town'])
        if address_info.get('StateOrProvince'):
            parts.append(address_info['StateOrProvince'])
        if address_info.get('Postcode'):
            parts.append(address_info['Postcode'])
        if address_info.get('Country', {}).get('Title'):
            parts.append(address_info['Country']['Title'])
            
        return ', '.join(parts) if parts else 'Unknown Address'
    
    def _process_connections(self, connections: List[Dict]) -> List[Dict]:
        """Process connection information."""
        processed_connections = []
        
        for conn in connections:
            connection_data = {
                'id': conn.get('ID'),
                'type': self._safe_get_nested(conn, ['ConnectionType', 'Title'], 'Unknown'),
                'level': self._safe_get_nested(conn, ['Level', 'Title'], 'Unknown'),
                'power_kw': conn.get('PowerKW'),
                'current_type': self._safe_get_nested(conn, ['CurrentType', 'Title'], 'Unknown'),
                'quantity': conn.get('Quantity', 1),
                'status': self._safe_get_nested(conn, ['StatusType', 'Title'], 'Unknown'),
                'comments': conn.get('Comments')
            }
            processed_connections.append(connection_data)
            
        return processed_connections
    
    def _get_connection_types(self, connections: List[Dict]) -> List[str]:
        """Get unique connection types."""
        types = set()
        for conn in connections:
            conn_type = self._safe_get_nested(conn, ['ConnectionType', 'Title'])
            if conn_type:
                types.add(conn_type)
        return list(types)
    
    def _get_power_levels(self, connections: List[Dict]) -> List[str]:
        """Get unique power levels."""
        levels = set()
        for conn in connections:
            level = self._safe_get_nested(conn, ['Level', 'Title'])
            if level:
                levels.add(level)
        return list(levels)
    
    def get_async(self, latitude: float, longitude: float, radius: float = 10.0, api_key: Optional[str] = None) -> APIWorker:
        """
        Get charging stations asynchronously.
        
        Returns:
            APIWorker thread that can be connected to signals
        """
        worker = APIWorker(self, latitude, longitude, radius, api_key)
        return worker

