try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from datetime import datetime
import os


class PDFExporter:
    """Handles PDF export functionality for charging stations."""
    
    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab library is not available. Please install it: pip install reportlab")
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom styles for the PDF."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        # Header style
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=12,
            textColor=colors.darkblue
        ))
        
        # Station name style
        self.styles.add(ParagraphStyle(
            name='StationName',
            parent=self.styles['Heading3'],
            fontSize=12,
            spaceAfter=6,
            spaceBefore=6,
            textColor=colors.darkgreen
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey
        ))
    
    def export_stations(self, stations, file_path):
        """
        Export charging stations to PDF.
        
        Args:
            stations: List of station dictionaries
            file_path: Output PDF file path
        """
        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Build the story (content)
        story = []
        
        # Title page
        story.extend(self._create_title_page(len(stations)))
        
        # Summary table
        if stations:
            story.extend(self._create_summary_table(stations))
        
        # Detailed station information
        for i, station in enumerate(stations):
            if i > 0:  # Add page break between stations (except first)
                story.append(PageBreak())
            story.extend(self._create_station_detail(station, i + 1))
        
        # Build PDF
        doc.build(story)
    
    def _create_title_page(self, station_count):
        """Create the title page."""
        story = []
        
        # Title
        title = Paragraph(
            "Electric Vehicle Charging Stations Report",
            self.styles['CustomTitle']
        )
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Generation info
        gen_info = [
            f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            f"Total Stations: {station_count}",
            "Data source: OpenChargeMap.org"
        ]
        
        for info in gen_info:
            p = Paragraph(info, self.styles['Normal'])
            story.append(p)
            story.append(Spacer(1, 12))
        
        story.append(Spacer(1, 40))
        
        # Description
        description = """
        This report contains detailed information about electric vehicle charging stations 
        found in your selected area. Each station entry includes location details, 
        operator information, connection types, and availability status.
        """
        
        desc_para = Paragraph(description, self.styles['Normal'])
        story.append(desc_para)
        story.append(PageBreak())
        
        return story
    
    def _create_summary_table(self, stations):
        """Create a summary table of all stations."""
        story = []
        
        # Section header
        header = Paragraph("Summary of Charging Stations", self.styles['CustomHeading'])
        story.append(header)
        story.append(Spacer(1, 12))
        
        # Prepare table data
        table_data = [
            ['#', 'Station Name', 'Distance (km)', 'Operator', 'Status', 'Connections']
        ]
        
        for i, station in enumerate(stations, 1):
            row = [
                str(i),
                station.get('name', 'Unknown')[:30] + ('...' if len(station.get('name', '')) > 30 else ''),
                f"{station.get('distance', 'N/A'):.1f}" if station.get('distance') else 'N/A',
                station.get('operator', 'Unknown')[:20] + ('...' if len(station.get('operator', '')) > 20 else ''),
                station.get('status', 'Unknown'),
                str(station.get('num_points', 0))
            ]
            table_data.append(row)
        
        # Create table
        table = Table(table_data, colWidths=[0.5*inch, 2.5*inch, 1*inch, 1.5*inch, 1*inch, 1*inch])
        
        # Style the table
        table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            
            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALTERNATEBACKGROUND', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        story.append(table)
        story.append(PageBreak())
        
        return story
    
    def _create_station_detail(self, station, station_num):
        """Create detailed information for a single station."""
        story = []
        
        # Station header
        station_title = f"Station {station_num}: {station.get('name', 'Unknown Station')}"
        title_para = Paragraph(station_title, self.styles['StationName'])
        story.append(title_para)
        story.append(Spacer(1, 12))
        
        # Basic information
        basic_info = [
            ('Location', station.get('address', 'Unknown')),
            ('Coordinates', f"{station.get('latitude', 'N/A')}, {station.get('longitude', 'N/A')}"),
            ('Distance', f"{station.get('distance', 'N/A'):.2f} km" if station.get('distance') else 'N/A'),
            ('Operator', station.get('operator', 'Unknown')),
            ('Status', station.get('status', 'Unknown')),
            ('Access Type', station.get('access_type', 'Unknown')),
            ('Number of Charging Points', str(station.get('num_points', 0))),
        ]
        
        # Create basic info table
        basic_table_data = []
        for label, value in basic_info:
            basic_table_data.append([f"{label}:", value])
        
        basic_table = Table(basic_table_data, colWidths=[2*inch, 4*inch])
        basic_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        story.append(basic_table)
        story.append(Spacer(1, 20))
        
        # Connection information
        connections = station.get('connections', [])
        if connections:
            conn_header = Paragraph("Connection Details", self.styles['CustomHeading'])
            story.append(conn_header)
            story.append(Spacer(1, 8))
            
            conn_table_data = [
                ['Type', 'Level', 'Power (kW)', 'Current', 'Quantity', 'Status']
            ]
            
            for conn in connections:
                row = [
                    conn.get('type', 'Unknown'),
                    conn.get('level', 'Unknown'),
                    str(conn.get('power_kw', 'N/A')),
                    conn.get('current_type', 'Unknown'),
                    str(conn.get('quantity', 1)),
                    conn.get('status', 'Unknown')
                ]
                conn_table_data.append(row)
            
            conn_table = Table(conn_table_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 0.8*inch, 1.2*inch])
            conn_table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                
                # Data
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALTERNATEBACKGROUND', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            
            story.append(conn_table)
            story.append(Spacer(1, 20))
        
        # Contact information
        contact_info = []
        if station.get('phone'):
            contact_info.append(('Phone', station.get('phone')))
        if station.get('email'):
            contact_info.append(('Email', station.get('email')))
        if station.get('url'):
            contact_info.append(('Website', station.get('url')))
        
        if contact_info:
            contact_header = Paragraph("Contact Information", self.styles['CustomHeading'])
            story.append(contact_header)
            story.append(Spacer(1, 8))
            
            contact_table_data = []
            for label, value in contact_info:
                contact_table_data.append([f"{label}:", value])
            
            contact_table = Table(contact_table_data, colWidths=[1.5*inch, 4.5*inch])
            contact_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ]))
            
            story.append(contact_table)
            story.append(Spacer(1, 20))
        
        # Additional information
        additional_info = []
        if station.get('cost') and station.get('cost') != 'Unknown':
            additional_info.append(('Cost', station.get('cost')))
        if station.get('comments'):
            additional_info.append(('Comments', station.get('comments')))
        if station.get('date_created'):
            additional_info.append(('Date Created', station.get('date_created')))
        if station.get('date_last_verified'):
            additional_info.append(('Last Verified', station.get('date_last_verified')))
        
        if additional_info:
            additional_header = Paragraph("Additional Information", self.styles['CustomHeading'])
            story.append(additional_header)
            story.append(Spacer(1, 8))
            
            for label, value in additional_info:
                info_text = f"<b>{label}:</b> {value}"
                info_para = Paragraph(info_text, self.styles['Normal'])
                story.append(info_para)
                story.append(Spacer(1, 6))
        
        return story

