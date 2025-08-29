# -*- coding: utf-8 -*-
"""
Dependency installer for ChargeSpot QGIS Plugin
"""

import os
import sys
import subprocess
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsMessageLog, Qgis


def install_dependencies():
    """Install required dependencies for the plugin."""
    
    dependencies = ['requests', 'reportlab']
    missing_deps = []
    
    # Check which dependencies are missing
    for dep in dependencies:
        try:
            __import__(dep)
        except ImportError:
            missing_deps.append(dep)
    
    if not missing_deps:
        return True
    
    # Ask user permission to install
    reply = QMessageBox.question(
        None,
        "Install Dependencies",
        f"ChargeSpot plugin requires the following Python packages:\n"
        f"{', '.join(missing_deps)}\n\n"
        f"Would you like to install them automatically?\n"
        f"(This may take a few minutes)",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes
    )
    
    if reply != QMessageBox.Yes:
        QMessageBox.warning(
            None,
            "Dependencies Required",
            f"The following packages are required for ChargeSpot to work:\n"
            f"{', '.join(missing_deps)}\n\n"
            f"Please install them manually:\n"
            f"pip install {' '.join(missing_deps)}"
        )
        return False
    
    # Try to install dependencies
    try:
        # Get the current plugin directory
        plugin_dir = os.path.dirname(__file__)
        libs_dir = os.path.join(plugin_dir, 'libs')
        
        # Create libs directory if it doesn't exist
        if not os.path.exists(libs_dir):
            os.makedirs(libs_dir)
        
        # Add libs directory to Python path
        if libs_dir not in sys.path:
            sys.path.insert(0, libs_dir)
        
        # Install each dependency
        for dep in missing_deps:
            QgsMessageLog.logMessage(
                f"Installing {dep}...",
                "ChargeSpot",
                Qgis.Info
            )
            
            # Try different pip commands
            pip_commands = [
                [sys.executable, "-m", "pip", "install", "--target", libs_dir, dep],
                ["pip", "install", "--target", libs_dir, dep],
                ["pip3", "install", "--target", libs_dir, dep]
            ]
            
            success = False
            for cmd in pip_commands:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minutes timeout
                    )
                    if result.returncode == 0:
                        success = True
                        QgsMessageLog.logMessage(
                            f"Successfully installed {dep}",
                            "ChargeSpot",
                            Qgis.Info
                        )
                        break
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    continue
            
            if not success:
                raise Exception(f"Failed to install {dep}")
        
        # Verify installation
        for dep in missing_deps:
            try:
                __import__(dep)
            except ImportError:
                raise Exception(f"Failed to import {dep} after installation")
        
        QMessageBox.information(
            None,
            "Installation Complete",
            f"Successfully installed all required dependencies:\n"
            f"{', '.join(missing_deps)}\n\n"
            f"ChargeSpot is now ready to use!"
        )
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        QgsMessageLog.logMessage(
            f"Dependency installation failed: {error_msg}",
            "ChargeSpot",
            Qgis.Critical
        )
        
        QMessageBox.critical(
            None,
            "Installation Failed",
            f"Failed to install dependencies automatically.\n\n"
            f"Error: {error_msg}\n\n"
            f"Please install manually:\n"
            f"pip install {' '.join(missing_deps)}\n\n"
            f"Or copy the packages to:\n"
            f"{libs_dir}"
        )
        
        return False


def check_dependencies():
    """Check if all dependencies are available."""
    dependencies = ['requests', 'reportlab']
    
    for dep in dependencies:
        try:
            __import__(dep)
        except ImportError:
            return False
    
    return True
