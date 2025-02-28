import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow
import logger_config
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

logger = logger_config.setup_logger(__name__)

class SingleApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self._server = None
        self._socket = QLocalSocket()
        self._socket.connectToServer("WordSearchSystem")
        
        if self._socket.waitForConnected():
            # 如果已经有实例在运行，则退出
            sys.exit(0)
        else:
            # 创建并启动服务器
            self._server = QLocalServer()
            self._server.removeServer("WordSearchSystem")
            self._server.listen("WordSearchSystem")

def main():
    app = SingleApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()