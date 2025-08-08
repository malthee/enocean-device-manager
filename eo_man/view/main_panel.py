import logging

from tkinter import *
from tkinter import ttk

from ..icons.image_gallary import ImageGallery

from ..controller.app_bus import AppBus, AppBusEventType
from ..controller.serial_controller import SerialController
from ..controller.gateway_registry import GatewayRegistry

from ..data.data_manager import DataManager

from ..view import DEFAULT_WINDOW_TITLE
from ..view.device_details import DeviceDetails
from ..view.device_table import DeviceTable
from ..view.filter_bar import FilterBar
from ..view.log_output import LogOutputPanel
from ..view.menu_presenter import MenuPresenter
from ..view.serial_communication_bar import SerialConnectionBar
from ..view.status_bar import StatusBar
from ..view.tool_bar import ToolBar

class MainPanel():

    def __init__(self, app_bus:AppBus, data_manager: DataManager, initial_config_file=None, initial_pct14_file=None):
        print(f"DEBUG: MainPanel.__init__ - Starting initialization")
        self.main = Tk()
        self.app_bus = app_bus
        self.data_manager = data_manager
        self.initial_config_file = initial_config_file
        self.initial_pct14_file = initial_pct14_file
        
        print(f"DEBUG: MainPanel.__init__ - Created Tk window")
        
        # Don't start event queue processing yet - wait until UI is fully initialized
        self.app_bus._tk_root = self.main  # Set reference without starting queue
        
        print(f"DEBUG: MainPanel.__init__ - Set tk_root reference")
        
        ## init main window
        self._init_window()
        
        print(f"DEBUG: MainPanel.__init__ - Window initialized")

        ## define grid
        row_button_bar = 0
        row_serial_con_bar = 1
        row_filter_bar = 2
        row_main_area = 3
        row_status_bar = 4
        self.main.rowconfigure(row_button_bar, weight=0, minsize=38)      # button bar
        self.main.rowconfigure(row_serial_con_bar, weight=0, minsize=38)      # serial connection bar
        self.main.rowconfigure(row_filter_bar, weight=0, minsize=38)      # table filter bar
        self.main.rowconfigure(row_main_area, weight=5, minsize=100)     # treeview
        # main.rowconfigure(2, weight=1, minsize=30)    # logview
        self.main.rowconfigure(row_status_bar, weight=0, minsize=30)      # status bar
        self.main.columnconfigure(0, weight=1, minsize=100)

        gateway_registry = GatewayRegistry(app_bus)
        serial_controller = SerialController(app_bus, gateway_registry)

        print(f"DEBUG: MainPanel.__init__ - Created controllers")

        ## init presenters
        mp = MenuPresenter(self.main, app_bus, data_manager, serial_controller)
        
        print(f"DEBUG: MainPanel.__init__ - Created MenuPresenter")
        
        ToolBar(self.main, mp, row=row_button_bar)
        print(f"DEBUG: MainPanel.__init__ - Created ToolBar")
        
        SerialConnectionBar(self.main, app_bus, data_manager, serial_controller, row=row_serial_con_bar)
        print(f"DEBUG: MainPanel.__init__ - Created SerialConnectionBar")
        
        FilterBar(self.main, app_bus, data_manager, row=row_filter_bar)
        print(f"DEBUG: MainPanel.__init__ - Created FilterBar")
        # main area
        main_split_area = ttk.PanedWindow(self.main, orient=VERTICAL)
        main_split_area.grid(row=row_main_area, column=0, sticky=NSEW, columnspan=4)
        
        data_split_area = ttk.PanedWindow(main_split_area, orient=HORIZONTAL)
        # data_split_area = Frame(main_split_area)
        # data_split_area.columnconfigure(0, weight=5)
        # data_split_area.columnconfigure(0, weight=0, minsize=100)
        
        print(f"DEBUG: MainPanel.__init__ - Creating DeviceTable")
        dt = DeviceTable(data_split_area, app_bus, data_manager)
        print(f"DEBUG: MainPanel.__init__ - Created DeviceTable")
        
        dd = DeviceDetails(self.main, data_split_area, app_bus, data_manager)
        print(f"DEBUG: MainPanel.__init__ - Created DeviceDetails")
        
        lo = LogOutputPanel(main_split_area, app_bus, data_manager)
        print(f"DEBUG: MainPanel.__init__ - Created LogOutputPanel")

        print(f"DEBUG: MainPanel.__init__ - Adding widgets to PanedWindows")
        main_split_area.add(data_split_area, weight=5)
        main_split_area.add(lo.root, weight=2)

        # Add widgets to data split area with proper weights
        data_split_area.add(dt.root, weight=5)
        data_split_area.add(dd.root, weight=1)  # Changed from weight=0 to weight=1
        print(f"DEBUG: MainPanel.__init__ - PanedWindow setup complete")
        print(f"DEBUG: MainPanel.__init__ - dt.root: {dt.root}")
        print(f"DEBUG: MainPanel.__init__ - dd.root: {dd.root}")
        print(f"DEBUG: MainPanel.__init__ - data_split_area children: {data_split_area.panes()}")
        print(f"DEBUG: MainPanel.__init__ - main_split_area children: {main_split_area.panes()}")
        
        # Force layout update
        print(f"DEBUG: MainPanel.__init__ - Forcing layout updates")
        main_split_area.update_idletasks()
        data_split_area.update_idletasks()
        
        # Try to set sash position to ensure both panes are visible
        def adjust_sash_positions():
            print("DEBUG: adjust_sash_positions - Starting sash adjustment")
            try:
                # Force layout updates first
                self.main.update_idletasks()
                data_split_area.update_idletasks()
                main_split_area.update_idletasks()
                
                # Get dimensions
                main_width = self.main.winfo_width()
                main_height = self.main.winfo_height()
                data_width = data_split_area.winfo_width()
                data_height = data_split_area.winfo_height()
                
                print(f"DEBUG: Main window: {main_width}x{main_height}")
                print(f"DEBUG: Data split area: {data_width}x{data_height}")
                print(f"DEBUG: Device table pane: {dt.root.winfo_width()}x{dt.root.winfo_height()}")
                print(f"DEBUG: Device details pane: {dd.root.winfo_width()}x{dd.root.winfo_height()}")
                
                # Set horizontal sash position (70% for device table, 30% for details)
                if data_width > 100:
                    sash_pos = int(data_width * 0.7)
                    data_split_area.sashpos(0, sash_pos)
                    print(f"DEBUG: Set data sash to position {sash_pos}")
                
                # Set vertical sash position (60% for data area, 40% for logs - more space for logs)
                if main_height > 100:
                    sash_pos = int(main_height * 0.6)  # Changed from 0.7 to 0.6
                    main_split_area.sashpos(0, sash_pos)
                    print(f"DEBUG: Set main sash to position {sash_pos}")
                    
                # Force another update
                self.main.update_idletasks()
                data_split_area.update_idletasks()
                main_split_area.update_idletasks()
                
                # Check final state
                print(f"DEBUG: Final device table pane: {dt.root.winfo_width()}x{dt.root.winfo_height()}")
                print(f"DEBUG: Final device details pane: {dd.root.winfo_width()}x{dd.root.winfo_height()}")
                
                # Check log panel dimensions too
                try:
                    log_width = main_split_area.winfo_width()
                    log_height = main_height - sash_pos if main_height > 100 else 0
                    print(f"DEBUG: Log panel area should be: {log_width}x{log_height}")
                except Exception as e:
                    print(f"DEBUG: Could not get log panel dimensions: {e}")
                
            except Exception as e:
                print(f"DEBUG: adjust_sash_positions - Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Schedule the adjustment after layout is complete
        self.main.after(200, adjust_sash_positions)
        print(f"DEBUG: MainPanel.__init__ - Scheduled sash position adjustment")
        # dt.root.grid(row=0, column=0, sticky="nsew")
        # dd.root.grid(row=0, column=1, sticky="nsew")

        StatusBar(self.main, app_bus, data_manager, row=row_status_bar)

        # Now that all UI components are created, start the event queue processing
        # This prevents race conditions on macOS during widget initialization
        self.app_bus._process_event_queue()

        # Start event queue processing after main window setup
        self.main.after(1, lambda: self.main.focus_force())
        self.main.after(10, self.on_loaded)

        ## start main loop
        self.main.mainloop()

        
        


    def _init_window(self):
        self.main.title(DEFAULT_WINDOW_TITLE)

        #style
        style = ttk.Style()
        style.configure("TButton", relief="sunken", background='green')
        style_theme = 'xpnative' # 'clam'
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Available style themes: {ttk.Style().theme_names()}", 'log-level': 'DEBUG'})
        try:
            style.theme_use(style_theme)
        except:
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Cannot load style theme {style_theme}!", 'log-level': 'WARNING'})

        self.main.geometry("1400x600")  # set starting size of window
        # self.main.attributes('-fullscreen', True)
        # self.main.state('zoomed') # opens window maximized

        self.main.config(bg="lightgrey")
        self.main.protocol("WM_DELETE_WINDOW", self.on_closing)

        # icon next to title in window frame
        self.main.wm_iconphoto(False, ImageGallery.get_eo_man_logo())

        # icon in taskbar
        icon = ImageGallery.get_eo_man_logo()
        self.main.iconphoto(True, icon, icon)

    def on_loaded(self) -> None:
        print(f"DEBUG: MainPanel.on_loaded - Window loaded, starting delayed data loading")
        
        # Load initial data after UI is fully initialized
        if self.initial_config_file:
            print(f"DEBUG: MainPanel.on_loaded - Loading config file: {self.initial_config_file}")
            self.data_manager.load_application_data_from_file(self.initial_config_file)
        elif self.initial_pct14_file:
            print(f"DEBUG: MainPanel.on_loaded - Loading PCT14 file: {self.initial_pct14_file}")
            import asyncio
            from ..data.pct14_data_manager import PCT14DataManager
            devices = asyncio.run(PCT14DataManager.get_devices_from_pct14(self.initial_pct14_file))
            self.data_manager.load_devices(devices)
            
        print(f"DEBUG: MainPanel.on_loaded - Firing WINDOW_LOADED event")
        self.app_bus.fire_event(AppBusEventType.WINDOW_LOADED, {})

    def on_closing(self) -> None:
        self.app_bus.fire_event(AppBusEventType.WINDOW_CLOSED, {})
        logging.info("Close Application eo-man")
        logging.info("========================\n")
        self.main.destroy()