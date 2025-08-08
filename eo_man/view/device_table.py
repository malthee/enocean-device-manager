import threading
import time
from tkinter import *
from tkinter import ttk

from ..controller.app_bus import AppBus, AppBusEventType
from ..data.const import *
from ..data.homeassistant.const import CONF_ID, CONF_NAME
from ..data.filter import DataFilter
from ..data.data_manager import DataManager, Device
from ..data import data_helper
from ..icons.image_gallary import ImageGallery

from eltakobus.util import b2s
from eltakobus.message import EltakoMessage, RPSMessage, Regular1BSMessage, Regular4BSMessage, EltakoWrappedRPS


class DeviceTable():

    ICON_SIZE = (20,20)
    NON_BUS_DEVICE_LABEL:str="Distributed Devices"

    def __init__(self, main: Tk, app_bus:AppBus, data_manager:DataManager):
        self.blinking_enabled = True
        self.pane = ttk.Frame(main, padding=2)
        # Don't use pack() when this will be added to a PanedWindow - conflicts with PanedWindow.add()
        self.root = self.pane

        # Scrollbar
        yscrollbar = ttk.Scrollbar(self.pane, orient=VERTICAL)
        yscrollbar.pack(side=RIGHT, fill=Y)

        xscrollbar = ttk.Scrollbar(self.pane, orient=HORIZONTAL)
        xscrollbar.pack(side=BOTTOM, fill=X)

        # Treeview
        columns = ("Address", "External Address", "Device Type", "Key Function", "Comment", "Export to HA Config", "HA Platform", "Device EEP", "Sender Address", "Sender EEP")
        self.treeview = ttk.Treeview(
            self.pane,
            show="tree headings", 
            selectmode="browse",
            yscrollcommand=yscrollbar.set,
            xscrollcommand=xscrollbar.set,
            columns=(0,1,2,3,4,5,6,7,8,9),
        )
        self.treeview.pack(expand=True, fill=BOTH)
        yscrollbar.config(command=self.treeview.yview)
        xscrollbar.config(command=self.treeview.xview)

        def sort_rows_in_treeview(tree:ttk.Treeview, col_i:int, descending:bool, partent:str=''):
            data = [(tree.set(item, col_i), item) for item in tree.get_children(partent)]
            data.sort(reverse=descending)
            for index, (val, item) in enumerate(data):
                tree.move(item, partent, index)
            
            for item in tree.get_children(partent):
                sort_rows_in_treeview(tree, col_i, descending, item)

        def sort_treeview(tree:ttk.Treeview, col:int, descending:bool):
            i = columns.index(col)
            for item in tree.get_children(''):
                sort_rows_in_treeview(tree, i, descending, item)
            tree.heading(i, command=lambda c=col, d=(not descending): sort_treeview(tree, c, d))

        self.treeview.column('#0', anchor="w", width=250, minwidth=250)#, stretch=NO)
        for col in columns:
            # Treeview headings
            i = columns.index(col)
            if col in ['Key Function']:
                self.treeview.column(i, anchor="w", width=250, minwidth=250)#, stretch=NO)
            else:
                self.treeview.column(i, anchor="w", width=80, minwidth=80)#, stretch=NO)
            self.treeview.heading(i, text=col, anchor="center", command=lambda c=col, d=False: sort_treeview(self.treeview, c, d))
        
        # self.menu = Menu(main, tearoff=0)
        # self.menu.add_command(label="Cut")
        # self.menu.add_command(label="Copy")
        # self.menu.add_command(label="Paste")
        # self.menu.add_command(label="Reload")
        # self.menu.add_separator()
        # self.menu.add_command(label="Rename")

        self.treeview.tag_configure('related_devices')
        self.treeview.tag_configure('blinking', background='lightblue')

        # self.treeview.bind('<ButtonRelease-1>', self.on_selected)
        self.treeview.bind('<<TreeviewSelect>>', self.on_selected)
        # self.treeview.bind("<Button-3>", self.show_context_menu)

        self.check_if_wireless_network_exists()

        self.current_data_filter:DataFilter = None
        self.app_bus = app_bus
        self.app_bus.add_event_handler(AppBusEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)
        self.app_bus.add_event_handler(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, self.update_device_representation_handler)
        self.app_bus.add_event_handler(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, self.update_sensor_representation_handler)
        self.app_bus.add_event_handler(AppBusEventType.LOAD_FILE, self._reset)
        self.app_bus.add_event_handler(AppBusEventType.SET_DATA_TABLE_FILTER, self._set_data_filter_handler)
        self.app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self._serial_callback_handler)

        self.data_manager = data_manager

        # initial loading
        print(f"DEBUG: DeviceTable.__init__ - Starting initialization")
        print(f"DEBUG: DeviceTable.__init__ - DataManager has {len(self.data_manager.devices)} devices")
        print(f"DEBUG: DeviceTable.__init__ - Device IDs: {list(self.data_manager.devices.keys())}")
        
        if self.data_manager.selected_data_filter_name is not None:
            print(f"DEBUG: DeviceTable.__init__ - Setting data filter: {self.data_manager.selected_data_filter_name}")
            self._set_data_filter_handler(self.data_manager.data_fitlers[self.data_manager.selected_data_filter_name])
            
        for d in self.data_manager.devices.values():
            parent = self.NON_BUS_DEVICE_LABEL if not d.is_bus_device() else None
            print(f"DEBUG: DeviceTable.__init__ - Adding device {d.external_id}, is_bus_device: {d.is_bus_device()}, parent: {parent}")
            self.update_device_handler(d, parent)
            
        print(f"DEBUG: DeviceTable.__init__ - Initial loading complete")
            
        # Schedule a delayed refresh to catch any missed events during initialization
        # This is particularly important on macOS where timing issues can occur
        if hasattr(self.app_bus, '_tk_root') and self.app_bus._tk_root:
            print(f"DEBUG: DeviceTable.__init__ - Scheduling delayed refresh")
            self.app_bus._tk_root.after(100, self._delayed_refresh)
            # Also schedule a debug check after all devices should be loaded
            self.app_bus._tk_root.after(2000, self._debug_treeview_state)
        else:
            print(f"DEBUG: DeviceTable.__init__ - No tk_root available for delayed refresh")


    def _delayed_refresh(self):
        """Force a refresh of the treeview to catch any display issues"""
        print(f"DEBUG: _delayed_refresh called")
        try:
            self.treeview.update()
            self.treeview.update_idletasks()
            total_items = len(self.treeview.get_children())
            print(f"DEBUG: _delayed_refresh - Total items after refresh: {total_items}")
            if total_items > 0:
                first_item = self.treeview.get_children()[0]
                print(f"DEBUG: _delayed_refresh - First item: {first_item}, text: {self.treeview.item(first_item, 'text')}")
                # Check if item is open/expanded
                children = self.treeview.get_children(first_item)
                print(f"DEBUG: _delayed_refresh - First item children: {len(children)}")
        except Exception as e:
            print(f"DEBUG: _delayed_refresh error: {e}")

    def _debug_treeview_state(self):
        """Comprehensive debug of treeview state"""
        print(f"DEBUG: === TREEVIEW STATE DEBUG ===")
        try:
            # Widget visibility
            print(f"DEBUG: Treeview widget: {self.treeview}")
            print(f"DEBUG: Widget visible: {self.treeview.winfo_viewable()}")
            print(f"DEBUG: Widget mapped: {self.treeview.winfo_ismapped()}")
            print(f"DEBUG: Widget width: {self.treeview.winfo_width()}")
            print(f"DEBUG: Widget height: {self.treeview.winfo_height()}")
            print(f"DEBUG: Widget x: {self.treeview.winfo_x()}")
            print(f"DEBUG: Widget y: {self.treeview.winfo_y()}")
            
            # Parent information
            print(f"DEBUG: Parent frame (pane): {self.pane}")
            print(f"DEBUG: Pane visible: {self.pane.winfo_viewable()}")
            print(f"DEBUG: Pane mapped: {self.pane.winfo_ismapped()}")
            print(f"DEBUG: Pane width: {self.pane.winfo_width()}")
            print(f"DEBUG: Pane height: {self.pane.winfo_height()}")
            print(f"DEBUG: Pane x: {self.pane.winfo_x()}")
            print(f"DEBUG: Pane y: {self.pane.winfo_y()}")
            
            # Data content
            all_children = self.treeview.get_children()
            print(f"DEBUG: Total root items: {len(all_children)}")
            
            for i, child in enumerate(all_children[:5]):  # Show first 5 items
                text = self.treeview.item(child, 'text')
                values = self.treeview.item(child, 'values')
                open_status = self.treeview.item(child, 'open')
                sub_children = self.treeview.get_children(child)
                print(f"DEBUG: Item {i}: {child} | Text: '{text}' | Values: {values} | Open: {open_status} | Children: {len(sub_children)}")
                
                # Show some sub-items if any
                for j, sub_child in enumerate(sub_children[:3]):
                    sub_text = self.treeview.item(sub_child, 'text')
                    sub_values = self.treeview.item(sub_child, 'values')
                    print(f"DEBUG:   Sub-item {j}: {sub_child} | Text: '{sub_text}' | Values: {sub_values}")
            
            # Column info
            columns = self.treeview['columns']
            print(f"DEBUG: Columns: {columns}")
            for col in columns:
                width = self.treeview.column(col, 'width')
                print(f"DEBUG: Column '{col}' width: {width}")
                
            # Try to force visibility
            print(f"DEBUG: Forcing update and focus...")
            self.treeview.update_idletasks()
            self.treeview.update()
            self.treeview.focus_set()
            
            # Force geometry updates on parent
            self.pane.update_idletasks()
            self.pane.update()
            
            # Re-check geometry after forced updates
            print(f"DEBUG: After forced updates:")
            print(f"DEBUG: Widget visible: {self.treeview.winfo_viewable()}")
            print(f"DEBUG: Widget mapped: {self.treeview.winfo_ismapped()}")
            print(f"DEBUG: Widget width: {self.treeview.winfo_width()}")
            print(f"DEBUG: Widget height: {self.treeview.winfo_height()}")
            print(f"DEBUG: Pane visible: {self.pane.winfo_viewable()}")
            print(f"DEBUG: Pane mapped: {self.pane.winfo_ismapped()}")
            print(f"DEBUG: Pane width: {self.pane.winfo_width()}")
            print(f"DEBUG: Pane height: {self.pane.winfo_height()}")
            
            # Check if we need to expand items to make them visible
            if len(all_children) > 0:
                print(f"DEBUG: Attempting to expand first item...")
                first_item = all_children[0]
                self.treeview.item(first_item, open=True)
                print(f"DEBUG: First item expanded, checking if it has visible children...")
                expanded_children = self.treeview.get_children(first_item)
                print(f"DEBUG: First item now has {len(expanded_children)} visible children")
                
                # Force another update after expansion
                self.treeview.update()
                
        except Exception as e:
            print(f"DEBUG: _debug_treeview_state error: {e}")
        print(f"DEBUG: === END TREEVIEW STATE DEBUG ===")


    def _set_data_filter_handler(self, filter):
        self.current_data_filter = filter

        self._reset(None)
        for d in self.data_manager.devices.values():
            if d.bus_device:
                self.update_device_handler(d)
            else:
                self.update_device_handler(d, parent=self.NON_BUS_DEVICE_LABEL)


    def _reset(self, data):
        for item in self.treeview.get_children():
            self.treeview.delete(item)
        self.check_if_wireless_network_exists()


    def on_selected(self, event):
        device_external_id = self.treeview.focus()
        device = self.data_manager.get_device_by_id(device_external_id)
        if device is not None:
            self.app_bus.fire_event(AppBusEventType.SELECTED_DEVICE, device)

        self.mark_related_elements(device_external_id)


    def mark_related_elements(self, device_external_id:str) -> None:
        for iid in self.treeview.tag_has( 'related_devices' ):
            self.treeview.item( iid, tags=() )

        devices = self.data_manager.get_related_devices(device_external_id)
        for d in devices:
            if self.treeview.exists(d.external_id):
                self.treeview.item(d.external_id, tags=('related_devices'))


    def show_context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()


    def insert_device(self, device:Device):
        v=("", b2s(device.address[0]), "", "")
        self.treeview.insert(parent="", index="end", text=device.id_string, values=v)

        
    def device_scan_status_handler(self, status:str):
        if status in ['STARTED']:
            #TODO: disable treeview or menue of it
            # self.treeview.config(state=DISABLED)
            pass
        elif status in ['FINISHED']:
            #TODO: enable treeview or menue of it
            # self.treeview.config(state=NORMAL)
            pass


    def add_fam14(self, d:Device):
        print(f"DEBUG: DeviceTable.add_fam14 called for {d.external_id}")
        if d.is_fam14():
            if not self.treeview.exists(d.base_id):
                print(f"DEBUG: DeviceTable.add_fam14 - Adding new FAM14 {d.base_id}")
                text = ""
                comment = ""
                text = d.name
                comment = d.comment if d.comment is not None else "" 
                in_ha = d.use_in_ha
                try:
                    self.treeview.insert(parent="", 
                                         index=0, 
                                         iid=d.external_id, 
                                         text=" " + text, 
                                         values=("", "", "", "", comment, in_ha, "", "", ""),
                                         image=ImageGallery.get_fam14_icon(self.ICON_SIZE),
                                         open=True)
                    print(f"DEBUG: DeviceTable.add_fam14 - Successfully added FAM14 {d.external_id}")
                except Exception as e:
                    print(f"ERROR: DeviceTable.add_fam14 - Failed to add FAM14 {d.external_id}: {e}")
            else:
                print(f"DEBUG: DeviceTable.add_fam14 - Updating existing FAM14 {d.base_id}")
                self.treeview.item(d.base_id, 
                                   text=" " + d.name, 
                                   values=("", "", "", "", d.comment, d.use_in_ha, "", "", ""),
                                   image=ImageGallery.get_fam14_icon(self.ICON_SIZE), 
                                   open=True)


    def check_if_wireless_network_exists(self):
        id = self.NON_BUS_DEVICE_LABEL
        if not self.treeview.exists(id):
            self.treeview.insert(parent="", 
                                 index="end", 
                                 iid=id, 
                                 text=" " + self.NON_BUS_DEVICE_LABEL, 
                                 values=("", "", "", "", "", "", "", "", ""), 
                                 image=ImageGallery.get_wireless_icon(self.ICON_SIZE),
                                 open=True)


    def update_device_representation_handler(self, device:Device):
        print(f"DEBUG: DeviceTable.update_device_representation_handler called for {device.external_id}")
        if device.bus_device and not device.is_bus_device():
            device.bus_device = False
        self.update_device_handler(device)


    def update_device_handler(self, d:Device, parent:str=None):
        print(f"DEBUG: DeviceTable.update_device_handler called for {d.external_id}, parent={parent}")

        if self.current_data_filter is not None and not self.current_data_filter.filter_device(d):
            print(f"DEBUG: DeviceTable.update_device_handler - Device {d.external_id} filtered out")
            return

        if not d.is_fam14():
            print(f"DEBUG: DeviceTable.update_device_handler - Processing non-FAM14 device {d.external_id}")
            in_ha = d.use_in_ha
            ha_pl = "" if d.ha_platform is None else d.ha_platform
            eep = "" if d.eep is None else d.eep
            device_type = "" if d.device_type is None else d.device_type
            key_func = "" if d.key_function is None else d.key_function
            comment = "" if d.comment is None else d.comment
            sender_adr = "" if 'sender' not in d.additional_fields else d.additional_fields['sender'][CONF_ID]
            sender_eep = "" if 'sender' not in d.additional_fields else d.additional_fields['sender'][CONF_EEP]
            
            if d.is_usb300():
                image = ImageGallery.get_usb300_icon(self.ICON_SIZE)
            elif d.is_fam_usb():
                image = ImageGallery.get_fam_usb_icon(self.ICON_SIZE)
            elif d.is_fgw14_usb():
                image = ImageGallery.get_fgw14_usb_icon(self.ICON_SIZE)
            elif d.is_ftd14():
                image = ImageGallery.get_ftd14_icon(self.ICON_SIZE)
            elif d.is_EUL_Wifi_gw():
                image = ImageGallery.get_eul_gateway_icon(self.ICON_SIZE)
            elif d.is_mgw():
                image = ImageGallery.get_mgw_piotek_icon(self.ICON_SIZE)
            else:
                image = ImageGallery.get_blank(self.ICON_SIZE)

            _parent = d.base_id if parent is None else parent
            print(f"DEBUG: DeviceTable.update_device_handler - Determined parent: {_parent}")
            
            if not self.treeview.exists(_parent): 
                print(f"DEBUG: DeviceTable.update_device_handler - Parent {_parent} doesn't exist, adding FAM14")
                self.add_fam14(self.data_manager.devices[_parent])
                
            if not self.treeview.exists(d.external_id):
                print(f"DEBUG: DeviceTable.update_device_handler - Adding device {d.external_id} to treeview under parent {_parent}")
                try:
                    self.treeview.insert(parent=_parent, 
                                         index="end", 
                                         iid=d.external_id, 
                                         text=" " + d.name, 
                                         values=(d.address, d.external_id, device_type, key_func, comment, in_ha, ha_pl, eep, sender_adr, sender_eep), 
                                         open=True)
                    self.treeview.item(d.external_id, image=image)
                    print(f"DEBUG: DeviceTable.update_device_handler - Successfully added device {d.external_id} to treeview")
                    
                    # Debug: Check if the item is actually in the treeview
                    items = self.treeview.get_children()
                    all_items = []
                    for item in items:
                        all_items.append(item)
                        all_items.extend(self.treeview.get_children(item))
                    print(f"DEBUG: DeviceTable.update_device_handler - Total items in treeview: {len(all_items)}")
                    print(f"DEBUG: DeviceTable.update_device_handler - Treeview items: {all_items}")
                    
                    # Force treeview update and refresh
                    self.treeview.update()
                    self.treeview.update_idletasks()
                except Exception as e:
                    print(f"ERROR: DeviceTable.update_device_handler - Failed to add device {d.external_id} to treeview: {e}")
            else:
                print(f"DEBUG: DeviceTable.update_device_handler - Updating existing device {d.external_id}")
                # update device
                self.treeview.item(d.external_id, 
                                   text=" " + d.name, 
                                   values=(d.address, d.external_id, device_type, key_func, comment, in_ha, ha_pl, eep, sender_adr, sender_eep), 
                                   image=image,
                                   open=True)
                if self.treeview.parent(d.external_id) != _parent:
                    self.treeview.move(d.external_id, _parent, 0)
        else:
            print(f"DEBUG: DeviceTable.update_device_handler - Processing FAM14 device {d.external_id}")
            self.add_fam14(d)
        # self.trigger_blinking(d.external_id)
            

    def _serial_callback_handler(self, data:dict):
        message:EltakoMessage = data['msg']
        current_base_id:str = data['base_id']

        if type(message) in [RPSMessage, Regular1BSMessage, Regular4BSMessage, EltakoWrappedRPS]:
            if isinstance(message.address, int):
                adr = data_helper.a2s(message.address)
            else: 
                adr = b2s(message.address)

            if not adr.startswith('00-00-00-'):
                self.trigger_blinking(adr)
            elif current_base_id is not None:
                d:Device = self.data_manager.find_device_by_local_address(adr, current_base_id)
                if d is not None:
                    self.trigger_blinking(d.external_id)


    def trigger_blinking(self, external_id:str):
        if not self.blinking_enabled:
            return
        
        def blink(ext_id:str):
            for i in range(0,2):
                if self.treeview.exists(ext_id):
                    tags = self.treeview.item(ext_id)['tags']
                    if 'blinking' in tags:
                        if isinstance(tags, str):
                            self.treeview.item(ext_id, tags=() )
                        else:
                            tags.remove('blinking')
                            self.treeview.item(ext_id, tags=tags )
                    else:
                        if isinstance(tags, str):
                            self.treeview.item(ext_id, tags=('blinking') )
                        else:
                            tags.append('blinking')
                            self.treeview.item(ext_id, tags=tags )
                    time.sleep(.5)

            if self.treeview.exists(ext_id):
                tags = self.treeview.item(ext_id)['tags']
                if 'blinking' in tags:
                    if isinstance(tags, str):
                        self.treeview.item(ext_id, tags=() )
                    else:
                        tags.remove('blinking')
                        self.treeview.item(ext_id, tags=tags )

        t = threading.Thread(target=lambda ext_id=external_id: blink(ext_id))
        t.start()


    def update_sensor_representation_handler(self, d:Device):
        print(f"DEBUG: DeviceTable.update_sensor_representation_handler called for {d.external_id}")
        self.update_device_handler(d, parent=self.NON_BUS_DEVICE_LABEL)