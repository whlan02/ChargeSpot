# ChargeSpot - QGIS Plugin for Electric Vehicle Charging Stations

ChargeSpot is a comprehensive QGIS plugin that helps you find and visualize electric vehicle charging stations using the OpenChargeMap API. The plugin provides an intuitive interface for searching, filtering, and exporting charging station data.

## Features

### Core Functionality
- **Interactive Map Search**: Click on the map to set search center point
- **Radius-based Search**: Define search area with customizable radius (1-200 km)
- **API Integration**: Uses OpenChargeMap.org API for real-time data
- **Optional API Key**: Support for API keys to increase rate limits

### Visualization & Data Management
- **Custom Map Symbols**: Different icons and colors based on station status
- **Detailed Information**: Comprehensive station details including:
  - Location and contact information
  - Operator and access type
  - Connection types and power levels
  - Current status and verification data
- **Smart Filtering**: Filter by access type, operator, status, connection type, or power level
- **Flexible Sorting**: Sort by distance, name, operator, status, or number of charging points

### Export & Reporting
- **PDF Export**: Generate professional reports of selected stations
- **Detailed Reports**: Include station summaries and comprehensive details
- **Customizable Selection**: Export all or selected stations

## Installation

### Prerequisites
- QGIS 3.0 or higher
- Python packages: `requests`, `reportlab`

### Installation Steps

1. **Download the Plugin**:
   - Download all plugin files to your QGIS plugins directory
   - Typically located at: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/ChargeSpot/`

2. **Install Dependencies**:
   ```bash
   pip install requests reportlab
   ```

3. **Enable the Plugin**:
   - Open QGIS
   - Go to Plugins → Manage and Install Plugins
   - Find "ChargeSpot" in the list and enable it

## Usage

### Basic Search
1. **Open the Plugin**: Click the ChargeSpot icon in the toolbar
2. **Set Center Point**: Click "Select on Map" and click on your desired search center
3. **Configure Search**: Set radius and maximum results
4. **Search**: Click "Search Charging Stations"

### Advanced Features

#### API Key Configuration
- Navigate to the "Settings" tab
- Enter your OpenChargeMap API key for higher rate limits
- API keys are optional but recommended for frequent use

#### Filtering and Sorting
- Use the "Results" tab to filter stations by various criteria
- Sort results by distance, name, operator, status, or number of charging points
- Apply multiple filters for precise results

#### Exporting Data
1. Select desired stations in the results table
2. Click "Export Selected to PDF"
3. Choose save location
4. Generate comprehensive PDF report

### Station Information
- Click "Info" button in results table for detailed station information
- View connection types, power levels, contact details, and more
- Access operator information and verification status

## API Information

This plugin uses the OpenChargeMap API:
- **Base URL**: https://api.openchargemap.io/v3/poi
- **Documentation**: https://openchargemap.org/site/develop/api
- **Rate Limits**: Higher limits available with free API key
- **Data**: Real-time charging station information worldwide

## File Structure

```
ChargeSpot/
├── __init__.py              # Plugin initialization
├── charge_spot.py           # Main plugin class
├── charge_spot_dialog.py    # User interface dialog
├── api_client.py           # OpenChargeMap API client
├── pdf_export.py           # PDF export functionality
├── resources.py            # Qt resources
├── metadata.txt            # Plugin metadata
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Troubleshooting

### Common Issues

1. **"No charging stations found"**:
   - Increase search radius
   - Try a different location
   - Check internet connection

2. **API errors**:
   - Verify internet connection
   - Consider using an API key for higher rate limits
   - Check OpenChargeMap service status

3. **PDF export fails**:
   - Ensure `reportlab` package is installed
   - Check file write permissions
   - Select at least one station before exporting

### Dependencies
If you encounter import errors, install required packages:
```bash
pip install requests reportlab
```

## Development

### Contributing
1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Test thoroughly
5. Submit a pull request

### Code Structure
- `charge_spot.py`: Main plugin logic and QGIS integration
- `charge_spot_dialog.py`: UI components and user interactions
- `api_client.py`: API communication and data processing
- `pdf_export.py`: Report generation functionality

## License

This plugin is released under the GNU General Public License v2. See the license headers in individual files for details.

## Credits

- **Data Provider**: OpenChargeMap.org community
- **QGIS**: Open source geographic information system
- **Python Libraries**: requests, reportlab, PyQt5

## Support

For issues, feature requests, or questions:
1. Check the troubleshooting section above
2. Review OpenChargeMap API documentation
3. Submit issues to the project repository

---

**Note**: This plugin is not officially affiliated with OpenChargeMap.org. It is an independent tool that uses their public API.

