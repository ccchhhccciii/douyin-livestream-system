"""
话术变体模板生成UI测试模块。
提供简单的UI界面测试话术变体模板生成功能。
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
from modules.script_generator.template_generator import TemplateGenerator

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 定义固定的火山引擎模型
DEFAULT_MODEL = "doubao-1-5-pro-32k-250115"

# 定义异步工作线程
class GenerationWorker(QThread):
    """异步变体模板生成工作线程，避免UI阻塞。"""
    
    progress_signal = pyqtSignal(int, int)  # 当前进度, 总数
    chunk_signal = pyqtSignal(str)  # 单个生成片段
    result_signal = pyqtSignal(str)  # 单个生成结果
    complete_signal = pyqtSignal(list)  # 所有生成结果列表
    error_signal = pyqtSignal(str)  # 错误信息
    
    def __init__(self, generator: TemplateGenerator, script_content: str, count: int):
        super().__init__()
        self.generator = generator
        self.script_content = script_content
        self.model_id = DEFAULT_MODEL  # 使用固定模型
        self.count = count
        self._is_running = True
    
    def run(self):
        """执行变体模板生成任务。"""
        results = []
        
        if not self._is_running:
            return

        try:
            for i in range(self.count):
                if not self._is_running:
                    break
                    
                self.progress_signal.emit(i, self.count)
                logger.info(f"开始生成第 {i+1}/{self.count} 份变体模板")
                
                # 处理流式生成
                if i == 0:  # 只在第一次生成时显示流式结果
                    full_response = ""
                    for chunk in self.generator.generate_template_stream(self.script_content, self.model_id):
                        if not self._is_running:
                            break
                        if chunk is not None:
                            self.chunk_signal.emit(chunk)
                            full_response += chunk
                    
                    if full_response and self._is_running:
                        results.append(full_response)
                        self.result_signal.emit(full_response)
                        logger.info(f"第 {i+1} 份变体模板生成完成，长度: {len(full_response)}")
                else:
                    # 后续模板使用非流式生成
                    single_result = self.generator.generate_template(self.script_content, self.model_id, 1)
                    if single_result and self._is_running:
                        results.extend(single_result)
                        self.result_signal.emit(single_result[0])
                        logger.info(f"第 {i+1} 份变体模板生成完成，长度: {len(single_result[0]) if single_result else 0}")
        
        except Exception as e:
            logger.exception(f"变体模板生成过程中出错: {e}")
            self.error_signal.emit(f"生成变体模板时出错: {e}")
        
        finally:
            if self._is_running:
                self.progress_signal.emit(self.count, self.count)
                self.complete_signal.emit(results)
                logger.info(f"变体模板生成任务完成，成功生成 {len(results)}/{self.count} 份变体模板")
    
    def stop(self):
        """停止生成任务。"""
        logger.info("正在停止变体模板生成任务...")
        self._is_running = False

class TemplateGeneratorUI(QMainWindow):
    """话术变体模板生成测试UI界面。"""
    
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
        self.generator = TemplateGenerator(
            ollama_client=None,
            volcengine_client=self.volcengine_client,
            base_dir=self.data_dir
        )
        
        # 其他初始化
        self.worker = None
        self.generated_templates = []
        self.current_product_id = ""
        self.current_script_id = ""
        
        # 设置UI
        self.setWindowTitle("抖音直播话术变体模板生成器 - 测试版")
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
        
        # 产品选择区域
        product_group = QGroupBox("产品选择")
        product_layout = QVBoxLayout(product_group)
        
        product_select_layout = QHBoxLayout()
        product_label = QLabel("产品:")
        self.product_combo = QComboBox()
        self.product_combo.setMinimumWidth(200)
        self.product_combo.addItem("选择产品...", None)
        self.refresh_product_button = QPushButton("刷新")
        
        product_select_layout.addWidget(product_label)
        product_select_layout.addWidget(self.product_combo)
        product_select_layout.addWidget(self.refresh_product_button)
        product_layout.addLayout(product_select_layout)
        
        # 话术选择区域
        script_select_layout = QHBoxLayout()
        script_label = QLabel("话术文件:")
        self.script_combo = QComboBox()
        self.script_combo.setMinimumWidth(200)
        self.script_combo.addItem("选择话术...", None)
        self.refresh_script_button = QPushButton("刷新")
        
        script_select_layout.addWidget(script_label)
        script_select_layout.addWidget(self.script_combo)
        script_select_layout.addWidget(self.refresh_script_button)
        product_layout.addLayout(script_select_layout)
        
        main_layout.addWidget(product_group)
        
        # 填充产品下拉框
        self._populate_product_combo()
        
        # 生成次数区域
        control_group = QGroupBox("生成设置")
        control_layout = QHBoxLayout(control_group)
        
        count_label = QLabel("生成次数:")
        self.count_spinbox = QSpinBox()
        self.count_spinbox.setMinimum(1)
        self.count_spinbox.setMaximum(10)
        self.count_spinbox.setValue(3)  # 默认为3次
        
        model_info_label = QLabel(f"使用模型: {DEFAULT_MODEL}")
        
        control_layout.addWidget(count_label)
        control_layout.addWidget(self.count_spinbox)
        control_layout.addStretch(1)
        control_layout.addWidget(model_info_label)
        
        main_layout.addWidget(control_group)
        
        # 话术内容显示区域
        script_content_label = QLabel("原始话术内容:")
        self.script_content_display = QTextEdit()
        self.script_content_display.setReadOnly(True)
        self.script_content_display.setPlaceholderText("选择产品和话术后，此处将显示原始话术内容")
        main_layout.addWidget(script_content_label)
        main_layout.addWidget(self.script_content_display, 1)
        
        # 变体模板预览区域
        preview_label = QLabel("变体模板预览:")
        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)
        main_layout.addWidget(preview_label)
        main_layout.addWidget(self.preview_output, 2)
        
        # 操作按钮区域
        buttons_layout = QHBoxLayout()
        self.generate_all_button = QPushButton("批量处理所有话术")
        self.generate_all_button.setEnabled(True)  # 默认启用批量处理按钮
        self.generate_button = QPushButton("生成变体模板")
        self.generate_button.setEnabled(False)  # 初始禁用，需要选择话术后才启用
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.save_button = QPushButton("保存")
        self.save_button.setEnabled(False)
        
        buttons_layout.addWidget(self.generate_all_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.generate_button)
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addWidget(self.save_button)
        
        main_layout.addLayout(buttons_layout)
        
        # 连接信号
        self.generate_button.clicked.connect(self.start_generation)
        self.stop_button.clicked.connect(self.stop_generation)
        self.save_button.clicked.connect(self.save_results)
        self.refresh_product_button.clicked.connect(self._populate_product_combo)
        self.refresh_script_button.clicked.connect(self._populate_script_combo)
        self.product_combo.currentIndexChanged.connect(self.on_product_selected)
        self.script_combo.currentIndexChanged.connect(self.on_script_selected)
        self.generate_all_button.clicked.connect(self.batch_generate)  # 连接批量处理按钮信号
        
        # 检查客户端状态并更新UI
        if not self.volcengine_client:
            self.generate_button.setEnabled(False)
            self.statusBar().showMessage("错误：火山引擎客户端初始化失败。请检查配置文件。")
        else:
            self.statusBar().showMessage(f"就绪。使用模型：{DEFAULT_MODEL}")
    
    def _populate_product_combo(self):
        """扫描products目录，填充产品下拉框。"""
        self.product_combo.clear()
        self.product_combo.addItem("选择产品...", None)
        
        products_dir = os.path.join(self.data_dir, "products")
        if not os.path.exists(products_dir):
            return
            
        try:
            product_ids = [d for d in os.listdir(products_dir) 
                         if os.path.isdir(os.path.join(products_dir, d))]
            
            if product_ids:
                for product_id in sorted(product_ids):
                    # 只添加有话术的产品
                    script_dir = os.path.join(products_dir, product_id, "script")
                    if os.path.exists(script_dir) and os.listdir(script_dir):
                        self.product_combo.addItem(product_id, product_id)
                
                logger.info(f"产品下拉框已填充 {self.product_combo.count()-1} 个产品")
        except Exception as e:
            logger.exception(f"扫描产品目录时出错: {e}")
    
    def _populate_script_combo(self):
        """填充话术下拉框。"""
        self.script_combo.clear()
        self.script_combo.addItem("选择话术...", None)
        
        product_id = self.current_product_id
        if not product_id:
            return
        
        try:
            scripts = self.generator.get_all_scripts(product_id)
            
            if scripts:
                for script_id, path in sorted(scripts.items()):
                    # 读取前50字符作为预览
                    preview = "无法读取内容"
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            preview = content[:50] + "..." if len(content) > 50 else content
                    except:
                        pass
                    
                    self.script_combo.addItem(f"{script_id} - {preview}", script_id)
                
                logger.info(f"话术下拉框已填充 {self.script_combo.count()-1} 个话术")
        except Exception as e:
            logger.exception(f"获取话术列表时出错: {e}")
    
    def on_product_selected(self, index):
        """当用户从下拉框选择产品时调用。"""
        if index <= 0:  # 跳过"选择产品..."选项
            self.current_product_id = ""
            self.script_combo.clear()
            self.script_combo.addItem("选择话术...", None)
            self.script_content_display.clear()
            self.generate_button.setEnabled(False)
            self.generate_all_button.setEnabled(False)  # 禁用批量处理按钮
            return
            
        product_id = self.product_combo.itemData(index)
        if product_id:
            self.current_product_id = product_id
            # 更新话术下拉框
            self._populate_script_combo()
            # 启用批量处理按钮
            self.generate_all_button.setEnabled(True)  # 启用批量处理按钮
    
    def on_script_selected(self, index):
        """当用户从下拉框选择话术时调用。"""
        if index <= 0:  # 跳过"选择话术..."选项
            self.current_script_id = ""
            self.script_content_display.clear()
            self.generate_button.setEnabled(False)
            return
            
        script_id = self.script_combo.itemData(index)
        if script_id:
            self.current_script_id = script_id
            # 加载话术内容
            self.load_script_content()
    
    def load_script_content(self):
        """加载选中的话术内容。"""
        if not self.current_product_id or not self.current_script_id:
            return
            
        content = self.generator.get_script_content(self.current_product_id, self.current_script_id)
        if content:
            self.script_content_display.setPlainText(content)
            self.generate_button.setEnabled(True)
            self.statusBar().showMessage(f"已加载话术 '{self.current_script_id}'")
            logger.info(f"已加载产品 '{self.current_product_id}' 的话术 '{self.current_script_id}'")
        else:
            self.script_content_display.clear()
            self.generate_button.setEnabled(False)
            self.statusBar().showMessage(f"无法加载话术 '{self.current_script_id}'")
    
    def start_generation(self):
        """开始生成变体模板。"""
        # 验证输入
        if not self.current_product_id or not self.current_script_id:
            QMessageBox.warning(self, "输入错误", "请选择产品和话术")
            return
        
        script_content = self.script_content_display.toPlainText().strip()
        if not script_content:
            QMessageBox.warning(self, "输入错误", "话术内容为空")
            return
        
        count = self.count_spinbox.value()
        
        # 清除上一次的结果
        self.preview_output.clear()
        self.generated_templates = []
        self.save_button.setEnabled(False)
        
        # 更新UI状态
        self.generate_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.statusBar().showMessage(f"正在使用模型 {DEFAULT_MODEL} 生成变体模板...")
        
        # 创建并启动工作线程
        self.worker = GenerationWorker(self.generator, script_content, count)
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
        """保存生成的变体模板。"""
        if not self.current_product_id or not self.generated_templates:
            QMessageBox.warning(self, "保存错误", "没有可保存的内容")
            return
        
        saved_count = 0
        for template in self.generated_templates:
            try:
                self.generator.save_template(self.current_product_id, template)
                saved_count += 1
            except Exception as e:
                logger.exception(f"保存变体模板时出错: {e}")
        
        QMessageBox.information(self, "保存成功", f"已成功保存 {saved_count}/{len(self.generated_templates)} 份变体模板")
        self.statusBar().showMessage(f"保存完成: {saved_count}/{len(self.generated_templates)} 份变体模板")
    
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
        if result not in self.generated_templates:
            self.generated_templates.append(result)
    
    def display_error(self, error):
        """显示错误信息。"""
        QMessageBox.warning(self, "生成错误", error)
        self.statusBar().showMessage(f"错误: {error}")
    
    def generation_complete(self, results):
        """生成任务完成。"""
        count = len(results)
        self.statusBar().showMessage(f"生成完成: {count} 份变体模板")
        
        # 更新生成结果列表
        self.generated_templates = results
        
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
                "保存变体模板", 
                f"已成功生成 {count} 份变体模板，是否立即保存?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if save_reply == QMessageBox.StandardButton.Yes:
                self.save_results()
    
    # 添加批量生成方法
    def batch_generate(self):
        """批量处理所有话术文件。"""
        if not self.current_product_id:
            QMessageBox.warning(self, "输入错误", "请选择产品")
            return
            
        script_dir = os.path.join(self.data_dir, "products", self.current_product_id, "script")
        if not os.path.exists(script_dir):
            QMessageBox.warning(self, "目录不存在", f"话术目录不存在: {script_dir}")
            return
            
        try:
            script_files = [f for f in os.listdir(script_dir) if f.endswith(".txt")]
            
            if not script_files:
                QMessageBox.warning(self, "没有话术", f"产品 '{self.current_product_id}' 没有可用的话术")
                return
                
            count_per_script = self.count_spinbox.value()
            
            # 创建templates目录（如果不存在）
            templates_dir = os.path.join(self.data_dir, "products", self.current_product_id, "templates")
            os.makedirs(templates_dir, exist_ok=True)
            
            total_generated = 0
            total_scripts = len(script_files)
            
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("批量处理进度")
            progress_dialog.setText(f"正在批量处理 {total_scripts} 个话术文件...\n请稍候...")
            progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress_dialog.show()
            QApplication.processEvents()
            
            # 逐个处理话术文件
            for i, script_file in enumerate(script_files):
                script_path = os.path.join(script_dir, script_file)
                script_id = os.path.splitext(script_file)[0]
                
                try:
                    # 加载话术内容
                    with open(script_path, 'r', encoding='utf-8') as f:
                        script_content = f.read()
                    
                    if not script_content.strip():
                        logger.warning(f"跳过空话术文件: {script_path}")
                        continue
                    
                    # 更新进度对话框
                    progress_dialog.setText(
                        f"正在处理: {i+1}/{total_scripts} - {script_file}\n"
                        f"正在生成: {count_per_script} 个变体模板"
                    )
                    QApplication.processEvents()
                    
                    # 生成变体模板
                    templates = []
                    
                    # 第一个模板使用流式生成，显示过程
                    template_stream = ""
                    for chunk in self.generator.generate_template_stream(script_content, DEFAULT_MODEL):
                        if chunk is not None:
                            template_stream += chunk
                    
                    if template_stream:
                        templates.append(template_stream)
                    
                    # 其余模板使用非流式生成
                    if count_per_script > 1:
                        additional_templates = self.generator.generate_template(
                            script_content, DEFAULT_MODEL, count_per_script - 1
                        )
                        if additional_templates:
                            templates.extend(additional_templates)
                    
                    # 保存生成的模板
                    for j, template in enumerate(templates):
                        if template:
                            if count_per_script == 1:
                                # 如果只生成一个模板，直接用原始ID
                                template_file = f"{script_id}.txt"
                            else:
                                # 否则，添加序号
                                template_file = f"{script_id}_{j+1:03d}.txt"
                            
                            template_path = os.path.join(templates_dir, template_file)
                            
                            with open(template_path, 'w', encoding='utf-8') as f:
                                f.write(template)
                                
                            total_generated += 1
                
                except Exception as e:
                    logger.exception(f"处理话术 {script_file} 时出错: {e}")
            
            progress_dialog.accept()
            
            QMessageBox.information(
                self, 
                "批量处理完成", 
                f"已成功生成 {total_generated} 份变体模板\n"
                f"保存位置: {templates_dir}"
            )
            
            self.statusBar().showMessage(f"批量处理完成: {total_generated} 份变体模板")
            
        except Exception as e:
            logger.exception(f"批量处理时出错: {e}")
            QMessageBox.critical(self, "批量处理错误", f"批量处理时出错:\n{e}")
    
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
    window = TemplateGeneratorUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
