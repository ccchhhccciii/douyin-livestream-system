"""
话术生成UI测试模块。
提供简单的UI界面测试话术生成功能。
"""

import sys
import os
import json
import logging
import configparser
from typing import List, Optional, Dict

# 配置PyQt导入
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox, QSpinBox,
    QFileDialog, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# 设置项目根目录，确保能够导入其他模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 导入核心模块
from core.volcengine_client import VolcengineClient
from modules.script_generator.script_generator import ScriptGenerator

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 定义固定的火山引擎模型
DEFAULT_MODEL = "doubao-1-5-pro-32k-250115"

# 定义异步工作线程
class GenerationWorker(QThread):
    """异步话术生成工作线程，避免UI阻塞。"""
    
    progress_signal = pyqtSignal(int, int)  # 当前进度, 总数
    chunk_signal = pyqtSignal(str)  # 单个生成片段
    result_signal = pyqtSignal(str)  # 单个生成结果
    complete_signal = pyqtSignal(list)  # 所有生成结果列表
    error_signal = pyqtSignal(str)  # 错误信息
    
    def __init__(self, generator: ScriptGenerator, product_info: str, count: int):
        super().__init__()
        self.generator = generator
        self.product_info = product_info
        self.model_id = DEFAULT_MODEL  # 使用固定模型
        self.count = count
        self._is_running = True
    
    def run(self):
        """执行话术生成任务。"""
        results = []
        
        if not self._is_running:
            return

        try:
            for i in range(self.count):
                if not self._is_running:
                    break
                    
                self.progress_signal.emit(i, self.count)
                logger.info(f"开始生成第 {i+1}/{self.count} 份话术")
                
                # 处理流式生成
                if i == 0:  # 只在第一次生成时显示流式结果
                    full_response = ""
                    for chunk in self.generator.generate_script_stream(self.product_info, self.model_id):
                        if not self._is_running:
                            break
                        if chunk is not None:
                            self.chunk_signal.emit(chunk)
                            full_response += chunk
                    
                    if full_response and self._is_running:
                        results.append(full_response)
                        self.result_signal.emit(full_response)
                        logger.info(f"第 {i+1} 份话术生成完成，长度: {len(full_response)}")
                else:
                    # 后续话术使用非流式生成
                    single_result = self.generator.generate_script(self.product_info, self.model_id, 1)
                    if single_result and self._is_running:
                        results.extend(single_result)
                        self.result_signal.emit(single_result[0])
                        logger.info(f"第 {i+1} 份话术生成完成，长度: {len(single_result[0]) if single_result else 0}")
        
        except Exception as e:
            logger.exception(f"话术生成过程中出错: {e}")
            self.error_signal.emit(f"生成话术时出错: {e}")
        
        finally:
            if self._is_running:
                self.progress_signal.emit(self.count, self.count)
                self.complete_signal.emit(results)
                logger.info(f"话术生成任务完成，成功生成 {len(results)}/{self.count} 份话术")
    
    def stop(self):
        """停止生成任务。"""
        logger.info("正在停止话术生成任务...")
        self._is_running = False

class ScriptGeneratorUI(QMainWindow):
    """话术生成测试UI界面。"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化配置和路径 - 使用绝对路径和显式编码
        self.config_path = os.path.join(project_root, "config.ini")
        self.data_dir = os.path.join(project_root, "data")
        
        # 创建data目录（如果不存在）
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        
        # 初始化客户端实例
        self.volcengine_client = self._init_volcengine_client()
        
        # 创建生成器实例
        self.generator = ScriptGenerator(
            ollama_client=None,
            volcengine_client=self.volcengine_client,
            base_dir=self.data_dir
        )
        
        # 其他初始化
        self.worker = None
        self.generated_scripts = []
        
        # 设置UI
        self.setWindowTitle("抖音直播话术生成器 - 测试版")
        self.setGeometry(100, 100, 800, 600)
        self._setup_ui()
    
    def _init_volcengine_client(self) -> Optional[VolcengineClient]:
        """初始化火山引擎客户端。"""
        try:
            client = VolcengineClient()
            client.client_type = "volcengine"  # 添加类型标识
            logger.info("火山引擎客户端初始化成功")
            return client
        except Exception as e:
            logger.exception(f"初始化火山引擎客户端时出错: {e}")
            QMessageBox.critical(self, "初始化错误", f"火山引擎客户端初始化失败：\n\n{e}\n\n请检查config.ini文件是否存在且配置正确。")
            return None
    
    def _setup_ui(self):
        """设置UI界面。"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 产品ID区域
        product_id_layout = QHBoxLayout()
        product_id_label = QLabel("产品ID:")
        self.product_id_input = QLineEdit()
        self.product_id_input.setPlaceholderText("输入产品ID，如：chenpi_001")
        
        # 添加产品选择下拉框
        self.product_combo = QComboBox()
        self.product_combo.setMinimumWidth(150)
        self.product_combo.addItem("选择已有产品...", None)
        self.load_product_button = QPushButton("加载")
        
        product_id_layout.addWidget(product_id_label)
        product_id_layout.addWidget(self.product_id_input)
        product_id_layout.addWidget(self.product_combo)
        product_id_layout.addWidget(self.load_product_button)
        main_layout.addLayout(product_id_layout)
        
        # 填充产品下拉框
        self._populate_product_combo()
        
        # 生成次数区域
        control_group = QGroupBox("生成次数")
        control_layout = QHBoxLayout(control_group)
        
        count_label = QLabel("生成次数:")
        self.count_spinbox = QSpinBox()
        self.count_spinbox.setMinimum(1)
        self.count_spinbox.setMaximum(50)
        self.count_spinbox.setValue(10)  # 默认为10次
        
        model_info_label = QLabel(f"使用模型: {DEFAULT_MODEL}")
        
        control_layout.addWidget(count_label)
        control_layout.addWidget(self.count_spinbox)
        control_layout.addStretch(1)
        control_layout.addWidget(model_info_label)
        
        main_layout.addWidget(control_group)
        
        # 产品信息输入区域
        product_info_label = QLabel("产品信息:")
        self.product_info_input = QTextEdit()
        self.product_info_input.setPlaceholderText("在这里输入产品基本信息")
        main_layout.addWidget(product_info_label)
        main_layout.addWidget(self.product_info_input, 1)
        
        # 话术预览区域
        preview_label = QLabel("话术预览:")
        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)
        main_layout.addWidget(preview_label)
        main_layout.addWidget(self.preview_output, 2)
        
        # 操作按钮区域
        buttons_layout = QHBoxLayout()
        self.generate_button = QPushButton("生成话术")
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.save_button = QPushButton("保存")
        self.save_button.setEnabled(False)
        
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.generate_button)
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addWidget(self.save_button)
        
        main_layout.addLayout(buttons_layout)
        
        # 连接信号
        self.generate_button.clicked.connect(self.start_generation)
        self.stop_button.clicked.connect(self.stop_generation)
        self.save_button.clicked.connect(self.save_results)
        self.load_product_button.clicked.connect(self.load_selected_product)
        self.product_combo.currentIndexChanged.connect(self.on_product_selected)
        
        # 检查客户端状态并更新UI
        if not self.volcengine_client:
            self.generate_button.setEnabled(False)
            self.statusBar().showMessage("错误：火山引擎客户端初始化失败。请检查配置文件。")
        else:
            self.statusBar().showMessage(f"就绪。使用模型：{DEFAULT_MODEL}")
    
    def _populate_product_combo(self):
        """扫描products目录，填充产品下拉框。"""
        self.product_combo.clear()
        self.product_combo.addItem("选择已有产品...", None)
        
        products_dir = os.path.join(self.data_dir, "products")
        if not os.path.exists(products_dir):
            return
            
        try:
            product_ids = [d for d in os.listdir(products_dir) 
                         if os.path.isdir(os.path.join(products_dir, d))]
            
            if product_ids:
                for product_id in sorted(product_ids):
                    self.product_combo.addItem(product_id, product_id)
                logger.info(f"产品下拉框已填充 {len(product_ids)} 个产品")
        except Exception as e:
            logger.exception(f"扫描产品目录时出错: {e}")
    
    def on_product_selected(self, index):
        """当用户从下拉框选择产品时调用。"""
        if index <= 0:  # 跳过"选择已有产品..."选项
            return
            
        product_id = self.product_combo.itemData(index)
        if product_id:
            self.product_id_input.setText(product_id)
            # 自动加载选中产品的信息
            self.load_selected_product()
    
    def load_selected_product(self):
        """加载选中产品的信息。"""
        # 优先使用输入框的ID
        product_id = self.product_id_input.text().strip()
        
        # 如果输入框为空，使用下拉框选中的项
        if not product_id:
            index = self.product_combo.currentIndex()
            if index > 0:
                product_id = self.product_combo.itemData(index)
            
        if not product_id:
            QMessageBox.warning(self, "未选择产品", "请输入产品ID或从下拉框选择产品")
            return
            
        # 加载产品信息
        product_info_path = os.path.join(self.data_dir, "products", product_id, "product_info.json")
        if not os.path.exists(product_info_path):
            QMessageBox.warning(self, "产品不存在", f"找不到产品信息文件: {product_info_path}")
            return
            
        try:
            with open(product_info_path, 'r', encoding='utf-8') as f:
                product_info = json.load(f)
                
            # 判断信息类型并显示
            if isinstance(product_info, dict):
                if "description" in product_info:
                    self.product_info_input.setPlainText(product_info["description"])
                else:
                    # 显示整个JSON
                    self.product_info_input.setPlainText(json.dumps(product_info, ensure_ascii=False, indent=2))
            elif isinstance(product_info, str):
                self.product_info_input.setPlainText(product_info)
            else:
                self.product_info_input.setPlainText(str(product_info))
                
            self.statusBar().showMessage(f"已加载产品 '{product_id}' 的信息")
            logger.info(f"已加载产品 '{product_id}' 的信息")
            
        except Exception as e:
            logger.exception(f"加载产品信息时出错: {e}")
            QMessageBox.critical(self, "加载错误", f"加载产品信息时出错:\n{e}")
    
    def start_generation(self):
        """开始生成话术。"""
        # 获取用户输入
        product_id = self.product_id_input.text().strip()
        product_info = self.product_info_input.toPlainText().strip()
        
        # 验证输入
        if not product_id:
            QMessageBox.warning(self, "输入错误", "请输入产品ID")
            return
        
        if not product_info:
            QMessageBox.warning(self, "输入错误", "请输入产品信息")
            return
        
        count = self.count_spinbox.value()
        
        # 保存产品信息
        try:
            self.generator.save_product_info(product_id, product_info)
            logger.info(f"产品信息已保存，ID: {product_id}")
            # 更新产品下拉框
            self._populate_product_combo()
            # 选中新保存的产品
            index = self.product_combo.findData(product_id)
            if index >= 0:
                self.product_combo.setCurrentIndex(index)
        except Exception as e:
            QMessageBox.critical(self, "保存错误", f"保存产品信息时出错: {e}")
            return
        
        # 清除上一次的结果
        self.preview_output.clear()
        self.generated_scripts = []
        self.save_button.setEnabled(False)
        
        # 更新UI状态
        self.generate_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.statusBar().showMessage(f"正在使用模型 {DEFAULT_MODEL} 生成话术...")
        
        # 创建并启动工作线程
        self.worker = GenerationWorker(self.generator, product_info, count)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.chunk_signal.connect(self.display_chunk)
        self.worker.result_signal.connect(self.display_result)
        self.worker.complete_signal.connect(self.generation_complete)
        self.worker.error_signal.connect(self.display_error)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()
    
    def stop_generation(self):
        """停止生成任务。"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.stop_button.setEnabled(False)
            self.statusBar().showMessage("正在停止生成任务...")
    
    def save_results(self):
        """保存生成的话术。"""
        product_id = self.product_id_input.text().strip()
        
        if not product_id or not self.generated_scripts:
            QMessageBox.warning(self, "保存错误", "没有可保存的内容")
            return
        
        saved_count = 0
        for script in self.generated_scripts:
            try:
                self.generator.save_script(product_id, script)
                saved_count += 1
            except Exception as e:
                logger.exception(f"保存话术时出错: {e}")
        
        QMessageBox.information(self, "保存成功", f"已成功保存 {saved_count}/{len(self.generated_scripts)} 份话术")
        self.statusBar().showMessage(f"保存完成: {saved_count}/{len(self.generated_scripts)} 份话术")
    
    def update_progress(self, current, total):
        """更新进度信息。"""
        self.statusBar().showMessage(f"正在生成: {current+1}/{total}")
    
    def display_chunk(self, chunk):
        """显示流式生成的片段。"""
        current_text = self.preview_output.toPlainText()
        self.preview_output.setPlainText(current_text + chunk)
        # 滚动到底部
        self.preview_output.verticalScrollBar().setValue(
            self.preview_output.verticalScrollBar().maximum()
        )
    
    def display_result(self, result):
        """显示单个生成结果。"""
        self.preview_output.setPlainText(result)
        if result not in self.generated_scripts:
            self.generated_scripts.append(result)
    
    def display_error(self, error):
        """显示错误信息。"""
        QMessageBox.warning(self, "生成错误", error)
        self.statusBar().showMessage(f"错误: {error}")
    
    def generation_complete(self, results):
        """生成任务完成。"""
        count = len(results)
        self.statusBar().showMessage(f"生成完成: {count} 份话术")
        
        # 更新生成结果列表
        self.generated_scripts = results
        
        # 更新UI状态
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(count > 0)
        
        # 如果只有一个结果，直接显示
        if count == 1:
            self.preview_output.setPlainText(results[0])
        
        # 提示保存
        if count > 0:
            save_reply = QMessageBox.question(
                self, 
                "保存话术", 
                f"已成功生成 {count} 份话术，是否立即保存?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if save_reply == QMessageBox.StandardButton.Yes:
                self.save_results()
    
    def worker_finished(self):
        """工作线程完成清理。"""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        
        # 确保UI状态正确
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)

def main():
    app = QApplication(sys.argv)
    window = ScriptGeneratorUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
