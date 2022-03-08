import sys
import comm
import time
import dummy_serial
from serial import Serial
from PyQt5 import QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QThread, QObject, pyqtSignal

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
        # Request button
        self.btn_request_frame = QPushButton("Request",self)
        self.btn_request_frame.resize(self.btn_request_frame.sizeHint())
        self.btn_request_frame.clicked.connect(self.evt_request_frame)
        #TODO deactivate request button until some ping function shows the serial device is "ready"
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
                break
        #raw_data = self.serial.readline()
        #TODO validate data frame
        #TODO new dialog that displays heatmap
    
    def serial_connection_lost(self):
        """Notifies user that serial connection has been lost."""
        self.update_terminal("<b>Serial connnection lost!</b>")


    def init_serial(self, port:str, baudrate:str):
        """Initializes the serial connection and the terminal updater thread."""
        if port == "Dummy":
            self.serial = dummy_serial.Dummy(dummy_serial.get_mode_from_str(baudrate))
        else:
            self.serial = Serial(port,baudrate = int(baudrate))

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
            reply = QMessageBox.question(self,"Exit?","A serial connection is active. Do you really want to exit?",QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
                return super().closeEvent(event)
            else:
                event.ignore()
        else:
            event.accept()
    
   
    
    



class SerialSetup(QDialog):
    """Serial port setup dialog."""
    def __init__(self, parent = None):
        super().__init__(parent=parent)
        # window settings
        self.parent = parent
        self.setWindowTitle("Serial Setup")
        self.setWindowIcon(self.style().standardIcon(getattr(QStyle,'SP_MessageBoxQuestion')))
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
            new_options = ["Choose a dummy mode..."] + dummy_serial.get_modes()
            self.cbb_Baudrate.addItems(new_options)
        else:
            self.cbb_Baudrate.clear()
            new_options = ["Choose a baudrate...            "] + comm.list_baudrates()
            self.cbb_Baudrate.addItems(new_options)
        if saved_selection in new_options:
            self.cbb_Baudrate.setCurrentText(saved_selection)