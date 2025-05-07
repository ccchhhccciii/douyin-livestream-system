"""
最终话术生成UI测试模块。
提供简单的UI界面测试变体模板解析和最终话术生成功能。
"""

import sys
import os
import json
import logging
import random
from typing import List, Optional, Dict, Any

# 配置PyQt导入
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox, QSpinBox,
    QFileDialog, QMessageBox, QGroupBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# 设置项目根目录，确保能够导入其他模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 导入核心模块
from modules.script_generator.template_parser import TemplateParser

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GenerationWorker(QThread):
    """异步最终话术生成工作线程，避免UI阻塞。"""
    
    progress_signal = pyqtSignal(int, int)  # 当前进度, 总数
    result_signal = pyqtSignal(str)  # 单个生成结果
    complete_signal = pyqtSignal(list)  # 所有生成结果列表
    error_signal = pyqtSignal(str)  # 错误信息
    
    def __init__(self, template_parser: TemplateParser, template_content: str, 
                count: int, strategy: str, memory_time: int = 3600):
        super().__init__()
        self.template_parser = template_parser
        self.template_content = template_content
        self.count = count
        self.strategy = strategy
        self.memory_time = memory_time
        self._is_running = True
    
    def run(self):
        """执行最终话术生成任务。"""
        results = []
        
        if not self._is_running:
            return

        try:
            # 设置解析器记忆时间
            self.template_parser.memory_time = self.memory_time
            
            for i in range(self.count):
                if not self._is_running:
                    break
                    
                self.progress_signal.emit(i, self.count)
                logger.info(f"开始生成第 {i+1}/{self.count} 份最终话术")
                
                # 使用选定策略解析模板
                final_script = self.template_parser.render_template(
                    self.template_content, 
                    strategy=self.strategy
                )
                
                if final_script and self._is_running:
                    results.append(final_script)
                    self.result_signal.emit(final_script)
                    logger.info(f"第 {i+1} 份最终话术生成完成，长度: {len(final_script)}")
        
        except Exception as e:
            logger.exception(f"最终话术生成过程中出错: {e}")
            self.error_signal.emit(f"生成最终话术时出错: {e}")
        
        finally:
            if self._is_running:
                self.progress_signal.emit(self.count, self.count)
                self.complete_signal.emit(results)
                logger.info(f"最终话术生成任务完成，成功生成 {len(results)}/{self.count} 份最终话术")
    
    def stop(self):
        """停止生成任务。"""
        logger.info("正在停止最终话术生成任务...")
        self._is_running = False


class FinalScriptGeneratorUI(QMainWindow):
    """最终话术生成测试UI界面。"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化路径
        self.data_dir = os.path.join(project_root, "data")
        
        # 创建data目录（如果不存在）
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
        
        # 创建解析器实例
        self.template_parser = TemplateParser()
        
        # 其他初始化
        self.worker = None
        self.generated_scripts = []
        self.current_product_id = ""
        self.current_template_id = ""
        self.current_template_content = ""
        
        # 设置UI
        self.setWindowTitle("抖音直播最终话术生成器 - 测试版")
        self.setGeometry(100, 100, 900, 700)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI界面。"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 产品选择区域
        product_group = QGroupBox("产品和模板选择")
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
        
        # 模板选择区域
        template_select_layout = QHBoxLayout()
        template_label = QLabel("变体模板:")
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(200)
        self.template_combo.addItem("选择模板...", None)
        self.refresh_template_button = QPushButton("刷新")
        
        template_select_layout.addWidget(template_label)
        template_select_layout.addWidget(self.template_combo)
        template_select_layout.addWidget(self.refresh_template_button)
        product_layout.addLayout(template_select_layout)
        
        main_layout.addWidget(product_group)
        
        # 填充产品下拉框
        self._populate_product_combo()
        
        # 生成设置区域
        settings_group = QGroupBox("生成设置")
        settings_layout = QVBoxLayout(settings_group)
        
        # 生成数量设置
        count_layout = QHBoxLayout()
        count_label = QLabel("生成数量:")
        self.count_spinbox = QSpinBox()
        self.count_spinbox.setMinimum(1)
        self.count_spinbox.setMaximum(50)
        self.count_spinbox.setValue(10)  # 默认为10个
        
        memory_label = QLabel("记忆时间(秒):")
        self.memory_spinbox = QSpinBox()
        self.memory_spinbox.setMinimum(0)
        self.memory_spinbox.setMaximum(86400)  # 最大1天
        self.memory_spinbox.setValue(3600)  # 默认1小时
        self.memory_spinbox.setSingleStep(600)  # 步长10分钟
        
        count_layout.addWidget(count_label)
        count_layout.addWidget(self.count_spinbox)
        count_layout.addStretch(1)
        count_layout.addWidget(memory_label)
        count_layout.addWidget(self.memory_spinbox)
        
        settings_layout.addLayout(count_layout)
        
        # 选择策略
        strategy_layout = QHBoxLayout()
        strategy_label = QLabel("选择策略:")
        
        self.strategy_group = QButtonGroup(self)
        self.random_radio = QRadioButton("随机选择")
        self.random_radio.setChecked(True)  # 默认选中
        self.rotation_radio = QRadioButton("轮换选择")
        self.weighted_radio = QRadioButton("权重选择(暂不支持)")
        self.weighted_radio.setEnabled(False)  # 暂时禁用权重选择
        
        self.strategy_group.addButton(self.random_radio, 1)
        self.strategy_group.addButton(self.rotation_radio, 2)
        self.strategy_group.addButton(self.weighted_radio, 3)
        
        strategy_layout.addWidget(strategy_label)
        strategy_layout.addWidget(self.random_radio)
        strategy_layout.addWidget(self.rotation_radio)
        strategy_layout.addWidget(self.weighted_radio)
        strategy_layout.addStretch(1)
        
        settings_layout.addLayout(strategy_layout)
        
        main_layout.addWidget(settings_group)
        
        # 模板内容显示区域
        template_content_label = QLabel("变体模板内容:")
        self.template_content_display = QTextEdit()
        self.template_content_display.setReadOnly(True)
        self.template_content_display.setPlaceholderText("选择产品和模板后，此处将显示变体模板内容")
        main_layout.addWidget(template_content_label)
        main_layout.addWidget(self.template_content_display, 1)
        
        # 变体模板分析区域
        analysis_group = QGroupBox("模板分析")
        analysis_layout = QHBoxLayout(analysis_group)
        
        self.analysis_display = QTextEdit()
        self.analysis_display.setReadOnly(True)
        self.analysis_display.setMaximumHeight(80)
        self.analyze_button = QPushButton("分析模板")
        self.analyze_button.setEnabled(False)
        
        analysis_layout.addWidget(self.analysis_display, 3)
        analysis_layout.addWidget(self.analyze_button, 1)
        
        main_layout.addWidget(analysis_group)
        
        # 最终话术预览区域
        preview_label = QLabel("最终话术预览:")
        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)
        self.preview_output.setPlaceholderText("生成的最终话术将显示在这里")
        main_layout.addWidget(preview_label)
        main_layout.addWidget(self.preview_output, 2)
        
        # 操作按钮区域
        buttons_layout = QHBoxLayout()
        self.generate_button = QPushButton("生成最终话术")
        self.generate_button.setEnabled(False)  # 初始禁用，需要选择模板后才启用
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.save_button = QPushButton("保存")
        self.save_button.setEnabled(False)
        self.generate_all_button = QPushButton("批量生成")
        self.generate_all_button.setEnabled(True)  # 默认启用批量生成按钮
        
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
        self.generate_all_button.clicked.connect(self.batch_generate)
        self.analyze_button.clicked.connect(self.analyze_template)
        self.refresh_product_button.clicked.connect(self._populate_product_combo)
        self.refresh_template_button.clicked.connect(self._populate_template_combo)
        self.product_combo.currentIndexChanged.connect(self.on_product_selected)
        self.template_combo.currentIndexChanged.connect(self.on_template_selected)
        
        # 初始状态
        self.statusBar().showMessage("就绪。请选择产品和变体模板。")
    
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
                    # 只添加有模板的产品
                    template_dir = os.path.join(products_dir, product_id, "templates")
                    if os.path.exists(template_dir) and os.listdir(template_dir):
                        self.product_combo.addItem(product_id, product_id)
                
                logger.info(f"产品下拉框已填充 {self.product_combo.count()-1} 个产品")
        except Exception as e:
            logger.exception(f"扫描产品目录时出错: {e}")
    
    def _populate_template_combo(self):
        """填充模板下拉框。"""
        self.template_combo.clear()
        self.template_combo.addItem("选择模板...", None)
        
        product_id = self.current_product_id
        if not product_id:
            return
        
        template_dir = os.path.join(self.data_dir, "products", product_id, "templates")
        if not os.path.exists(template_dir):
            return
            
        try:
            template_files = [f for f in os.listdir(template_dir) if f.endswith(".txt")]
            
            if template_files:
                for template_file in sorted(template_files):
                    # 读取前50字符作为预览
                    preview = "无法读取内容"
                    template_path = os.path.join(template_dir, template_file)
                    try:
                        with open(template_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            preview = content[:50] + "..." if len(content) > 50 else content
                    except:
                        pass
                    
                    self.template_combo.addItem(f"{template_file} - {preview}", template_file)
                
                logger.info(f"模板下拉框已填充 {self.template_combo.count()-1} 个模板")
        except Exception as e:
            logger.exception(f"获取模板列表时出错: {e}")
    
    def on_product_selected(self, index):
        """当用户从下拉框选择产品时调用。"""
        if index <= 0:  # 跳过"选择产品..."选项
            self.current_product_id = ""
            self.template_combo.clear()
            self.template_combo.addItem("选择模板...", None)
            self.template_content_display.clear()
            self.generate_button.setEnabled(False)
            self.analyze_button.setEnabled(False)
            self.generate_all_button.setEnabled(False)  # 禁用批量生成按钮
            return
            
        product_id = self.product_combo.itemData(index)
        if product_id:
            self.current_product_id = product_id
            # 更新模板下拉框
            self._populate_template_combo()
            # 启用批量生成按钮
            self.generate_all_button.setEnabled(True)  # 始终启用批量生成按钮
    
    def on_template_selected(self, index):
        """当用户从下拉框选择模板时调用。"""
        if index <= 0:  # 跳过"选择模板..."选项
            self.current_template_id = ""
            self.current_template_content = ""
            self.template_content_display.clear()
            self.analysis_display.clear()
            self.generate_button.setEnabled(False)
            self.analyze_button.setEnabled(False)
            return
            
        template_id = self.template_combo.itemData(index)
        if template_id:
            self.current_template_id = template_id
            # 加载模板内容
            self.load_template_content()
    
    def load_template_content(self):
        """加载选中的模板内容。"""
        if not self.current_product_id or not self.current_template_id:
            return
            
        template_path = os.path.join(
            self.data_dir, "products", self.current_product_id, 
            "templates", self.current_template_id
        )
        
        if not os.path.exists(template_path):
            self.statusBar().showMessage(f"模板文件不存在: {template_path}")
            return
            
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            self.current_template_content = content
            self.template_content_display.setPlainText(content)
            self.generate_button.setEnabled(True)
            self.analyze_button.setEnabled(True)
            self.statusBar().showMessage(f"已加载模板 '{self.current_template_id}'")
            logger.info(f"已加载产品 '{self.current_product_id}' 的模板 '{self.current_template_id}'")
            
            # 清除分析结果
            self.analysis_display.clear()
            
        except Exception as e:
            logger.exception(f"加载模板内容时出错: {e}")
            self.statusBar().showMessage(f"加载模板时出错: {e}")
    
    def analyze_template(self):
        """分析当前模板结构。"""
        if not self.current_template_content:
            return
            
        try:
            # 分析模板
            analysis = self.template_parser.analyze_template(self.current_template_content)
            
            # 格式化分析结果
            analysis_text = (
                f"变体标记数量: {analysis['variant_count']} | "
                f"变体选项总数: {analysis['option_count']} | "
                f"平均选项数: {analysis['average_options']:.1f} | "
                f"最大选项数: {analysis['max_options']} | "
                f"嵌套变体数: {analysis['nested_count']} | "
                f"潜在组合数: {analysis['potential_combinations']:,}"
            )
            
            self.analysis_display.setPlainText(analysis_text)
            logger.info(f"模板分析完成: {analysis_text}")
            
        except Exception as e:
            logger.exception(f"分析模板时出错: {e}")
            self.analysis_display.setPlainText(f"分析出错: {e}")
    
    def get_selected_strategy(self) -> str:
        """获取选中的选择策略。"""
        selected_id = self.strategy_group.checkedId()
        
        if selected_id == 1:
            return TemplateParser.STRATEGY_RANDOM
        elif selected_id == 2:
            return TemplateParser.STRATEGY_ROTATION
        elif selected_id == 3:
            return TemplateParser.STRATEGY_WEIGHTED
        else:
            return TemplateParser.STRATEGY_RANDOM  # 默认随机
    
    def start_generation(self):
        """开始生成最终话术。"""
        # 验证输入
        if not self.current_product_id or not self.current_template_id:
            QMessageBox.warning(self, "输入错误", "请选择产品和模板")
            return
        
        if not self.current_template_content:
            QMessageBox.warning(self, "输入错误", "模板内容为空")
            return
        
        count = self.count_spinbox.value()
        memory_time = self.memory_spinbox.value()
        strategy = self.get_selected_strategy()
        
        # 清除上一次的结果
        self.preview_output.clear()
        self.generated_scripts = []
        self.save_button.setEnabled(False)
        
        # 更新UI状态
        self.generate_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.statusBar().showMessage(f"正在使用策略 {strategy} 生成最终话术...")
        
        # 创建并启动工作线程
        self.worker = GenerationWorker(
            self.template_parser, 
            self.current_template_content,
            count,
            strategy,
            memory_time
        )
        self.worker.progress_signal.connect(self.update_progress)
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
    
    def batch_generate(self):
        """批量生成所有模板的最终话术。"""
        if not self.current_product_id:
            QMessageBox.warning(self, "输入错误", "请选择产品")
            return
            
        template_dir = os.path.join(self.data_dir, "products", self.current_product_id, "templates")
        if not os.path.exists(template_dir):
            QMessageBox.warning(self, "目录不存在", f"模板目录不存在: {template_dir}")
            return
            
        try:
            template_files = [f for f in os.listdir(template_dir) if f.endswith(".txt")]
            
            if not template_files:
                QMessageBox.warning(self, "没有模板", f"产品 '{self.current_product_id}' 没有可用的模板")
                return
                
            count_per_template = self.count_spinbox.value()
            memory_time = self.memory_spinbox.value()
            strategy = self.get_selected_strategy()
            
            # 创建final_script目录（如果不存在）
            final_script_dir = os.path.join(self.data_dir, "products", self.current_product_id, "final_script")
            os.makedirs(final_script_dir, exist_ok=True)
            
            total_generated = 0
            total_templates = len(template_files)
            
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("批量生成进度")
            progress_dialog.setText(f"正在批量生成 {total_templates} 个模板的最终话术...\n请稍候...")
            progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress_dialog.show()
            QApplication.processEvents()
            
            # 逐个处理模板
            for i, template_file in enumerate(template_files):
                template_path = os.path.join(template_dir, template_file)
                
                try:
                    # 加载模板内容
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template_content = f.read()
                    
                    # 设置解析器记忆时间
                    self.template_parser.memory_time = memory_time
                    
                    # 生成指定数量的最终话术
                    for j in range(count_per_template):
                        # 更新进度对话框
                        progress_dialog.setText(
                            f"正在处理: {i+1}/{total_templates} - {template_file}\n"
                            f"正在生成: {j+1}/{count_per_template}"
                        )
                        QApplication.processEvents()
                        
                        # 生成最终话术
                        final_script = self.template_parser.render_template(
                            template_content, 
                            strategy=strategy
                        )
                        
                        if final_script:
                            # 保存最终话术
                            template_base = os.path.splitext(template_file)[0]
                            final_script_file = f"{template_base}_{j+1:03d}.txt"
                            final_script_path = os.path.join(final_script_dir, final_script_file)
                            
                            with open(final_script_path, 'w', encoding='utf-8') as f:
                                f.write(final_script)
                                
                            total_generated += 1
                
                except Exception as e:
                    logger.exception(f"处理模板 {template_file} 时出错: {e}")
            
            progress_dialog.accept()
            
            QMessageBox.information(
                self, 
                "批量生成完成", 
                f"已成功生成 {total_generated} 份最终话术\n"
                f"保存位置: {final_script_dir}"
            )
            
            self.statusBar().showMessage(f"批量生成完成: {total_generated} 份最终话术")
            
        except Exception as e:
            logger.exception(f"批量生成时出错: {e}")
            QMessageBox.critical(self, "批量生成错误", f"批量生成时出错:\n{e}")
    
    def save_results(self):
        """保存生成的最终话术。"""
        if not self.current_product_id or not self.generated_scripts:
            QMessageBox.warning(self, "保存错误", "没有可保存的内容")
            return
        
        # 创建final_script目录（如果不存在）
        final_script_dir = os.path.join(
            self.data_dir, "products", self.current_product_id, "final_script"
        )
        os.makedirs(final_script_dir, exist_ok=True)
        
        saved_count = 0
        for i, script in enumerate(self.generated_scripts):
            try:
                # 使用模板ID和序号作为文件名
                template_base = os.path.splitext(self.current_template_id)[0]
                final_script_file = f"{template_base}_{i+1:03d}.txt"
                final_script_path = os.path.join(final_script_dir, final_script_file)
                
                with open(final_script_path, 'w', encoding='utf-8') as f:
                    f.write(script)
                    
                saved_count += 1
                logger.info(f"已保存最终话术: {final_script_path}")
                
            except Exception as e:
                logger.exception(f"保存最终话术时出错: {e}")
        
        QMessageBox.information(
            self, 
            "保存成功", 
            f"已成功保存 {saved_count}/{len(self.generated_scripts)} 份最终话术\n"
            f"保存位置: {final_script_dir}"
        )
        
        self.statusBar().showMessage(f"保存完成: {saved_count}/{len(self.generated_scripts)} 份最终话术")
    
    def update_progress(self, current, total):
        """更新进度信息。"""
        self.statusBar().showMessage(f"正在生成: {current+1}/{total}")
    
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
        self.statusBar().showMessage(f"生成完成: {count} 份最终话术")
        
        # 更新生成结果列表
        self.generated_scripts = results
        
        # 更新UI状态
        self.generate_button.setEnabled(True)
        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(count > 0)
        
        # 如果有多个结果，显示最后一个
        if count > 0:
            self.preview_output.setPlainText(results[-1])
        
        # 提示保存
        if count > 0:
            save_reply = QMessageBox.question(
                self, 
                "保存最终话术", 
                f"已成功生成 {count} 份最终话术，是否立即保存?",
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
        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    window = FinalScriptGeneratorUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
