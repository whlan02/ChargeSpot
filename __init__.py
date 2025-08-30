def classFactory(iface):
    # Check and install dependencies
    try:
        import requests
        import reportlab
    except ImportError:
        from .dependency_installer import install_dependencies
        install_dependencies()
    
    from .charge_spot import ChargeSpot
    return ChargeSpot(iface)

