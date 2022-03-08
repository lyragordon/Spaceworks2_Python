from math import fabs
import sys
import comm
import time
import dummy_serial
from serial import Serial
from PyQt5 import QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QThread, QObject, pyqtSignal, QTimer
from PyQt5 import QtCore

class TerminalThread(QObject):
    """Thread that pushes lines to the terminal display"""
    progress = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self,serial:Serial):
        super().__init__()
        self.serial = serial

    def run(self):
        while self.serial.isOpen():
            if self.serial.inWaiting() > 0:
                line = self.serial.readline().decode('utf-8')
                self.progress.emit(line)
        self.finished.emit()


class MainWindow(QMainWindow):
    """Main window dialog."""
    def __init__(self,parent=None):
        super().__init__(parent=parent)
        # window settings
        self.setWindowTitle("SW2")
        self.setWindowIcon(self.style().standardIcon(getattr(QStyle,'SP_CommandLink')))
        self.serial = None
        # prompt for serial config
        self.dlg_serial_setup = SerialSetup(self)
        # Request button that's only active when ping is reciprocated
        self.btn_request_frame = QPushButton("Request",self)
        self.btn_request_frame.resize(self.btn_request_frame.sizeHint())
        self.btn_request_frame.clicked.connect(self.evt_request_frame)
        self.btn_request_frame.setEnabled(False)
        self.ping_timer = QTimer()
        self.ping_timer.setInterval(comm.PING_INTERVAL)
        self.ping_timer.timeout.connect(self.ping_serial)
        self.ping_timer.start()
        # Reset button
        self.btn_reset_serial = QPushButton("Reset",self)
        self.btn_reset_serial.resize(self.btn_reset_serial.sizeHint())
        self.btn_reset_serial.clicked.connect(self.evt_reset_serial)
        # Terminal display
        self.terminal = QTextBrowser(self)
        self.terminal_thread = QThread()
        # Display widgets stacked vertically
        self.vert_layout = QVBoxLayout(self)
        self.vert_layout.addWidget(self.btn_request_frame)
        self.vert_layout.addWidget(self.btn_reset_serial)
        self.vert_layout.addWidget(self.terminal)
        self.window = QWidget(self)
        self.window.setLayout(self.vert_layout)
        self.window.show()
        # window settings
        self.setCentralWidget(self.window)
        
        self.show()
        
    def update_terminal(self, line:str):
        """Adds a line to the terminal display."""
        self.terminal.append(line)
        self.terminal.resize(self.terminal.sizeHint())
        self.vert_layout.update()

    def evt_reset_serial(self):
        """Resets the serial port on a hardware level."""
        if self.serial and not isinstance(self.serial,dummy_serial.Dummy):
            self.serial.setDTR(False)
            time.sleep(0.5)
            self.serial.setDTR(True)
            time.sleep(0.5)
            
    def evt_request_frame(self):
        """Requests a data frame over serial and displays it."""
        self.serial.write(comm.REQUEST_COMMAND)
        timeout = time.time() + comm.REQUEST_TIMEOUT
        while self.serial.inWaiting() == 0:
            time.sleep(1)
            if time.time() > timeout:
                self.update_terminal("<b>REQUEST TIMEOUT</b>")
                return
        #raw_data = self.serial.readline()
        #TODO validate data frame
        #TODO new dialog that displays heatmap
    
    def serial_connection_lost(self):
        """Notifies user that serial connection has been lost."""
        self.update_terminal("<b>Serial connnection lost!</b>")
        self.evt_serial_connection_error()


    def init_serial(self, port:str, baudrate:str):
        """Initializes the serial connection and the terminal updater thread."""
        if port == "Dummy":
            self.serial = dummy_serial.Dummy(dummy_serial.get_mode_from_str(baudrate))
        else:
            try:
                self.serial = Serial(port,baudrate = int(baudrate))
            except:
                self.evt_serial_connection_error()
                return

        self.terminal_worker = TerminalThread(self.serial)
        self.terminal_worker.moveToThread(self.terminal_thread)
        self.terminal_thread.started.connect(self.terminal_worker.run)
        self.terminal_worker.finished.connect(self.serial_connection_lost)
        self.terminal_worker.finished.connect(self.terminal_worker.deleteLater)
        self.terminal_thread.finished.connect(self.terminal_thread.deleteLater)
        self.terminal_worker.progress.connect(self.update_terminal)
        self.terminal_thread.start()


    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.serial:
            reply = QMessageBox.question(self,"Exit?","A serial connection is active.\nDo you really want to exit?",QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
                return super().closeEvent(event)
            else:
                event.ignore()
        else:
            event.accept()

    def evt_serial_connection_error(self):
        self.serial = None
        self.terminal_thread = None
        self.terminal_worker = None
        error = QMessageBox.critical(self, "Serial Error", "The serial connection has encountered an error.")
        SerialSetup(self)
    
    def ping_serial(self):
        """Pings serial object and enables request button if it's active"""
        # This one's a bit of a doozy so I'll comment it fully
        if self.serial and self.serial.isOpen():
            # Send 'ping'
            self.serial.write(comm.PING_COMMAND)
            # Wait for a response (this should be done in a QThread....)
            timeout = time.process_time() + comm.PING_TIMEOUT
            while self.serial.inWaiting() == 0:
                if time.process_time() > timeout:
                    self.btn_request_frame.setEnabled(False)
                    self.update_terminal("<b>PING TIMEOUT</b>")
                    return
            # Read as many lines as are available, one of which may be the 'pong'
            raw_lines = self.serial.readlines()
            # If the 'pong' is in those lines, enable the button and pass the rest of the lines to the terminal
            if comm.PING_RESPONSE in raw_lines:
                self.btn_request_frame.setEnabled(True)
                if len(raw_lines) > 1:
                    other_lines = raw_lines.pop(raw_lines.index(comm.PING_RESPONSE))
                    for line in other_lines:
                        self.update_terminal(line.decode('utf-8'))
            # If the 'pong' isnt in those lines, just pass them to the terminal and deactivate the button
            else:
                self.btn_request_frame.setEnabled(False)
                for line in raw_lines:
                    self.update_terminal(line.decode('utf-8'))
        else:
            self.btn_request_frame.setEnabled(False)

    
    



class SerialSetup(QDialog):
    """Serial port setup dialog."""
    def __init__(self, parent = None):
        super().__init__(parent=parent)
        # window settings
        self.parent = parent
        self.setWindowTitle("Serial Setup")
        self.setWindowIcon(self.style().standardIcon(getattr(QStyle,'SP_MessageBoxQuestion')))
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint) 
        # ok button
        self.btn_Ok = QPushButton("Ok",self)
        self.btn_Ok.clicked.connect(self.evt_btn_Ok)
        # cancel button
        self.btn_Cancel = QPushButton("Cancel",self)
        self.btn_Cancel.clicked.connect(self.evt_btn_Cancel)
        # refresh button
        self.btn_Refresh = QPushButton(self.style().standardIcon(getattr(QStyle,'SP_BrowserReload')),"",self)
        self.btn_Refresh.clicked.connect(self.evt_btn_Refresh)
        # serial port selection dropdown
        self.cbb_SerialPort = QComboBox(self)
        self.update_cbb_SerialPort()
        self.cbb_SerialPort.activated.connect(self.evt_cbb_SerialPort_activated)
        # baudrate selection menu
        self.cbb_Baudrate = QComboBox(self)
        self.update_cbb_Baudrate()
        # simple horizontal layout
        self.horiz_layout = QHBoxLayout()
        self.horiz_layout.addWidget(self.btn_Refresh)
        self.horiz_layout.addWidget(self.cbb_SerialPort)
        self.horiz_layout.addWidget(self.cbb_Baudrate)
        self.horiz_layout.addWidget(self.btn_Ok)
        self.horiz_layout.addWidget(self.btn_Cancel)
        self.setLayout(self.horiz_layout)
        # window settings
        self.resize(self.sizeHint())
        self.show()

    def evt_btn_Ok(self):
        """If none of the default entries are selected, passes serial port info to main window and closes."""
        if self.cbb_SerialPort.currentText() != "Choose a serial port..." and "Choose" not in self.cbb_Baudrate.currentText():
            self.parent.init_serial(self.cbb_SerialPort.currentText(), self.cbb_Baudrate.currentText())
            self.close()

    def evt_btn_Refresh(self):
        """Refresh button updates dropdowns"""
        self.update_cbb_SerialPort()
        self.update_cbb_Baudrate()

    def evt_btn_Cancel(self):
        """Closes the app when 'cancel' is selected"""
        self.parent.close()

    def evt_cbb_SerialPort_activated(self):
        """Triggered when serialport dropdown is used."""
        self.update_cbb_Baudrate()
        self.update_cbb_SerialPort()

    def update_cbb_SerialPort(self):
        """Reloads the serialport dropdown. We want to do this on every interaction to keep the serial port list up-to-date."""
        saved_selection = self.cbb_SerialPort.currentText()
        new_options = ["Choose a serial port..."] + comm.list_serial_ports()
        self.cbb_SerialPort.clear()
        self.cbb_SerialPort.addItems(new_options)
        if saved_selection in new_options:
            self.cbb_SerialPort.setCurrentText(saved_selection)

    def update_cbb_Baudrate(self):
        """Reloads the baudrate dropdown to reflect the serialport dropdown."""
        saved_selection = self.cbb_Baudrate.currentText()
        if self.cbb_SerialPort.currentText() == "Dummy":
            self.cbb_Baudrate.clear()
            new_options = ["Choose a dummy mode...   "] + dummy_serial.get_modes()
            self.cbb_Baudrate.addItems(new_options)
        else:
            self.cbb_Baudrate.clear()
            new_options = ["Choose a baudrate...            "] + comm.list_baudrates()
            self.cbb_Baudrate.addItems(new_options)
        if saved_selection in new_options:
            self.cbb_Baudrate.setCurrentText(saved_selection)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        if not self.parent.serial:
            self.parent.close()
        return super().closeEvent(a0)
