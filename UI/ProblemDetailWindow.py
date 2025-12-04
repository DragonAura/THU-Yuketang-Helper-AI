import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import os
import json
from PIL import Image, ImageTk
from dashscope import MultiModalConversation

class ProblemDetailWindow:
    """问题详情窗口"""
    def __init__(self, master, problem):
        self.window = tk.Toplevel(master)
        self.window.title(f"问题详情 - 页码: {problem.get('page', 'N/A')}")
        self.window.geometry("900x700")
        self.problem = problem
        
        # 创建UI组件
        self.create_ui()
        
        # 初始化AI key输入框的值
        self.load_ai_key()
    
    def load_ai_key(self):
        # 从配置中加载AI key
        try:
            from Scripts.Utils import get_config_path
            config_path = get_config_path()
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    ai_key = config.get("ai_config", {}).get("api_key", "")
                    self.ai_key_entry.delete(0, tk.END)
                    self.ai_key_entry.insert(0, ai_key)
        except Exception as e:
            # 如果加载失败，使用环境变量作为备选
            ai_key = os.getenv("API_KEY_QWEN", "")
            self.ai_key_entry.delete(0, tk.END)
            self.ai_key_entry.insert(0, ai_key)
    
    def create_ui(self):
        # 创建主框架
        main_frame = tk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建滚动区域框架
        scroll_frame = tk.Frame(main_frame)
        scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建垂直滚动条
        y_scrollbar = ttk.Scrollbar(scroll_frame)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建水平滚动条
        x_scrollbar = ttk.Scrollbar(scroll_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 创建Canvas
        self.canvas = tk.Canvas(scroll_frame, yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 配置滚动条
        y_scrollbar.config(command=self.canvas.yview)
        x_scrollbar.config(command=self.canvas.xview)
        
        # 创建内部内容框架
        content_frame = tk.Frame(self.canvas)
        canvas_window = self.canvas.create_window((0, 0), window=content_frame, anchor="nw")
        
        # 绑定事件，确保Canvas大小适应内容
        def on_frame_configure(event):
            # 更新Canvas的滚动区域
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        content_frame.bind("<Configure>", on_frame_configure)
        
        # 绑定鼠标滚轮事件实现垂直滚动
        def on_mousewheel(event):
            try:
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError:
                # 忽略画布已被销毁的错误
                pass

        self.canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # 第一行：问题内容
        section_frame = tk.Frame(content_frame)
        section_frame.pack(fill=tk.X, pady=5)
        
        content_label = tk.Label(section_frame, text="问题内容:", font=("STHeiti", 12, "bold"))
        content_label.pack(anchor=tk.W)
        
        problem_content = tk.Text(section_frame, font=("STHeiti", 10), wrap=tk.WORD, height=3)
        problem_content.pack(fill=tk.X, expand=True, pady=5)
        problem_content.insert(tk.END, self.problem.get('body', '无问题内容'))
        problem_content.config(state=tk.DISABLED)
        
        # 第二行：问题图片
        section_frame = tk.Frame(content_frame)
        section_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        image_label = tk.Label(section_frame, text="问题图片:", font=("STHeiti", 12, "bold"))
        image_label.pack(anchor=tk.W)
        
        # 图片容器
        self.image_container = tk.Label(section_frame)
        self.image_container.pack(fill=tk.BOTH, expand=True)
        
        # 尝试加载并显示图片
        self.load_and_display_image()
        
        # 第三行：AI答题按钮和key输入
        section_frame = tk.Frame(content_frame)
        section_frame.pack(fill=tk.X, pady=5)
        
        ai_label = tk.Label(section_frame, text="AI答题:", font=("STHeiti", 12, "bold"))
        ai_label.pack(anchor=tk.W)
        
        # AI key输入和按钮
        input_frame = tk.Frame(section_frame)
        input_frame.pack(fill=tk.X, pady=5)
        
        key_label = tk.Label(input_frame, text="AI Key:", font=("STHeiti", 10))
        key_label.pack(side=tk.LEFT, padx=5)
        
        self.ai_key_entry = tk.Entry(input_frame, font=("STHeiti", 10), width=40, show="*")
        self.ai_key_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.ai_answer_btn = tk.Button(input_frame, text="AI 答题", font=("STHeiti", 10), 
                                     command=self.on_ai_answer_click)
        self.ai_answer_btn.pack(side=tk.RIGHT, padx=5)
        
        # 第四行：根据problemType渲染答题区域
        section_frame = tk.Frame(content_frame)
        section_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        answer_label = tk.Label(section_frame, text="您的答案:", font=("STHeiti", 12, "bold"))
        answer_label.pack(anchor=tk.W)
        
        # 根据问题类型创建不同的答题区域
        self.answer_vars = []
        self.answer_entries = []
        
        if self.problem.get('problemType') == 1:  # 单选题
            self.create_radio_answer_area(section_frame)
        elif self.problem.get('problemType') == 2 or self.problem.get('problemType') == 3:  # 多选题
            self.create_check_answer_area(section_frame)
        elif self.problem.get('blanks') or self.problem.get('problemType') == 5:  # 填空题
            self.create_fill_answer_area(section_frame)
        
        # 第五行：取消/确认按钮
        section_frame = tk.Frame(content_frame)
        section_frame.pack(fill=tk.X, pady=20)
        
        self.cancel_btn = tk.Button(section_frame, text="取消", font=("STHeiti", 10), 
                                  width=15, command=self.on_cancel_click)
        self.cancel_btn.pack(side=tk.RIGHT, padx=10)
        
        self.confirm_btn = tk.Button(section_frame, text="确认", font=("STHeiti", 10), 
                                  width=15, command=self.on_confirm_click)
        self.confirm_btn.pack(side=tk.RIGHT, padx=10)

    def on_cancel_click(self):
        """取消按钮点击事件"""
        # 解绑鼠标滚轮事件
        try:
            self.canvas.unbind_all("<MouseWheel>")
        except:
            pass
        self.window.destroy()

    def on_confirm_click(self):
        """确认按钮点击事件"""
        # 根据问题类型读取当前UI中的答案
        if self.problem.get('problemType') == 1:  # 单选题
            answer = [self.answer_var.get()]
        elif self.problem.get('problemType') == 2 or self.problem.get('problemType') == 3:  # 多选题
            answer = [key for key, var in self.answer_vars if var.get()]
        elif self.problem.get('blanks') or self.problem.get('problemType') == 5:  # 填空题
            answer = [entry.get() for entry in self.answer_entries]
        
        # 将答案写回到原始的problem对象
        self.problem['answers'] = answer
        
        messagebox.showinfo("提示", "答案已保存")
        
        # 解绑鼠标滚轮事件
        try:
            self.canvas.unbind_all("<MouseWheel>")
        except:
            pass
        self.window.destroy()

    def _update_answer_ui(self, ai_answer):
        # 根据问题类型更新答案UI
        if not ai_answer:
            messagebox.showinfo("提示", "AI未返回有效答案")
            return
        
        if self.problem.get('problemType') == 1:  # 单选题
            if ai_answer:
                self.answer_var.set(ai_answer[0])
        elif self.problem.get('problemType') == 2 or self.problem.get('problemType') == 3:  # 多选题
            # 先取消所有选择
            for key, var in self.answer_vars:
                var.set(False)
            
            # 根据AI答案选择对应的选项
            for key, var in self.answer_vars:
                if key in ai_answer:
                    var.set(True)
        elif self.problem.get('blanks') or self.problem.get('problemType') == 5:  # 填空题
            for i, entry in enumerate(self.answer_entries):
                if i < len(ai_answer):
                    entry.delete(0, tk.END)
                    entry.insert(0, ai_answer[i])
        
        messagebox.showinfo("提示", "AI答题完成，请点击确认保存答案")

    def load_and_display_image(self):
        # 尝试加载并显示图片
        image_path = self.problem.get('image', '')
        if image_path and os.path.exists(image_path):
            try:
                # 打开图片
                image = Image.open(image_path)
                # 调整图片大小以适应窗口
                max_width = 800
                max_height = 400
                width, height = image.size
                ratio = min(max_width/width, max_height/height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                image = image.resize((new_width, new_height), Image.LANCZOS)
                
                # 转换为tkinter可用的图片
                photo = ImageTk.PhotoImage(image)
                
                # 保存引用，防止被垃圾回收
                self.image_photo = photo
                
                # 显示图片
                self.image_container.config(image=photo)
            except Exception as e:
                self.image_container.config(text=f"图片加载失败: {str(e)}")
        else:
            self.image_container.config(text="无图片")
    
    def create_radio_answer_area(self, parent):
        # 创建单选题答题区域
        options = self.problem.get('options', [])
        default_answer = self.problem.get('answers', [])[0] if self.problem.get('answers') else ''
        
        self.answer_var = tk.StringVar(value=default_answer)
        
        for option in options:
            key = option.get('key', '')
            value = option.get('value', '')
            
            frame = tk.Frame(parent)
            frame.pack(fill=tk.X, padx=10, pady=2)
            
            radio = tk.Radiobutton(frame, text=f"{key}: {value}", variable=self.answer_var, value=key, 
                                 font=("STHeiti", 10), anchor=tk.W)
            radio.pack(fill=tk.X, padx=10)
    
    def create_check_answer_area(self, parent):
        # 创建多选题答题区域
        options = self.problem.get('options', [])
        default_answers = self.problem.get('answers', [])
        
        self.answer_vars = []
        
        for option in options:
            key = option.get('key', '')
            value = option.get('value', '')
            
            var = tk.BooleanVar(value=key in default_answers)
            self.answer_vars.append((key, var))
            
            frame = tk.Frame(parent)
            frame.pack(fill=tk.X, padx=10, pady=2)
            
            check = tk.Checkbutton(frame, text=f"{key}: {value}", variable=var, 
                                 font=("STHeiti", 10), anchor=tk.W)
            check.pack(fill=tk.X, padx=10)
    
    def create_fill_answer_area(self, parent):
        # 创建填空题答题区域
        blanks_count = len(self.problem.get('blanks', [""]))
        default_answers = self.problem.get('answers', [])
        
        self.answer_entries = []
        
        for i in range(blanks_count):
            frame = tk.Frame(parent)
            frame.pack(fill=tk.X, padx=10, pady=2)
            
            label = tk.Label(frame, text=f"填空{i+1}: ", font=("STHeiti", 10), width=10, anchor=tk.W)
            label.pack(side=tk.LEFT, padx=5)
            
            entry = tk.Entry(frame, font=("STHeiti", 10))
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            # 设置默认值
            if i < len(default_answers):
                entry.delete(0, tk.END)
                entry.insert(0, default_answers[i])
            
            self.answer_entries.append(entry)
    
    def on_ai_answer_click(self):
        # AI答题按钮点击事件
        # 获取AI key
        ai_key = self.ai_key_entry.get()
        if not ai_key:
            # 如果没有输入key，显示一个提示
            messagebox.showwarning("提示", "请输入AI Key")
            return
        
        # 模拟AI思考过程
        self.ai_answer_btn.config(state=tk.DISABLED, text="AI 思考中...")
        self.window.update()
        
        # 启动一个线程来调用AI接口，避免阻塞UI
        ai_thread = threading.Thread(target=self._call_ai_api, args=(ai_key,))
        ai_thread.daemon = True
        ai_thread.start()
    
    def _call_ai_api(self, ai_key):
        try:
            # 这里应该实现真正的AI API调用逻辑
            # 参考Classes.py中的get_problems方法
            image_path = self.problem.get('image', '')
            
            if image_path and os.path.exists(image_path):
                # 构建消息
                messages = [
                    {"role": "system", "content": [{"text": "You are a helpful assistant."}]},
                    {
                        'role':'user',
                        'content': [
                            {'image': f"file://{os.path.abspath(image_path)}"},
                            {'text': '请以JSON格式回答图片中的问题。如果是选择题，则返回{{"question": "问题", "answer": ["选项（A/B/C/...）"]}}，选项为圆形则为单选，选项为矩形则为多选；如果是填空题，则返回{{"question": "问题", "answer": ["填空1答案", "填空2答案", ...]}}；如果是主观题，则返回{{"question": "问题", "answer": ["主观题答案"]}}'}
                        ]
                    }
                ]
                
                # 实际的API调用
                response = MultiModalConversation.call(
                    api_key=ai_key,
                    model='qwen-vl-max-latest',
                    messages=messages,
                    response_format={"type": "json_object"},
                    vl_high_resolution_images=True)
                
                # 解析API返回结果
                json_output = response["output"]["choices"][0]["message"].content[0]["text"]
                res = json.loads(json_output)
                
                # 获取答案
                ai_answer = res.get('answer', [])
                
                # 在主线程中更新UI
                self.window.after(0, self._update_answer_ui, ai_answer)
            else:
                # 没有图片的情况，只使用文本问题
                # 这里可以实现纯文本的API调用
                messagebox.showinfo("提示", "该问题没有图片，无法使用AI答题功能")
                
        except json.JSONDecodeError as e:
            # JSON解析错误处理
            self.window.after(0, lambda: messagebox.showerror("错误", f"AI返回结果解析失败: {str(e)}"))
        except Exception as e:
            # 其他错误处理
            self.window.after(0, lambda: messagebox.showerror("错误", f"AI答题失败: {str(e)}"))
        finally:
            # 在主线程中恢复按钮状态
            self.window.after(0, lambda: self.ai_answer_btn.config(state=tk.NORMAL, text="AI 答题"))