import requests
import threading
import random
import time
from urllib3.util import retry
import websocket
import json
from Scripts.Utils import get_user_info, dict_result, calculate_waittime
import os
from dashscope import MultiModalConversation
import tkinter as tk
from tkinter import ttk
from typing import List, Union, Optional

import sys
from typing import List, Union, Optional

wss_url = "wss://pro.yuketang.cn/wsapp/"
class Lesson:
    def __init__(self,lessonid,lessonname,classroomid,main_ui):
        self.classroomid = classroomid
        self.lessonid = lessonid
        self.lessonname = lessonname
        self.sessionid = main_ui.config["sessionid"]
        self.headers = {
            "Cookie":"sessionid=%s" % self.sessionid,
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
        }
        self.receive_danmu = {}
        self.sent_danmu_dict = {}
        self.danmu_dict = {}
        self.problems_ls = []
        self.unlocked_problem = []
        self.classmates_ls = []
        self.add_message = main_ui.add_message
        # 在tkinter中，我们直接调用main_ui的方法来更新课程表格
        self.config = main_ui.config
        self.main_ui = main_ui
        code, rtn = get_user_info(self.sessionid)
        self.user_uid = rtn["id"]
        self.user_uname = rtn["name"]
        self.main_ui = main_ui

    def _get_ppt(self,presentationid):
        # 获取课程各页ppt
        r = requests.get(url="https://pro.yuketang.cn/api/v3/lesson/presentation/fetch?presentation_id=%s" % (presentationid),headers=self.headers,proxies={"http": None,"https":None})
        return dict_result(r.text)["data"]

    def get_problems(self,presentationid):
        # 获取课程ppt中的题目
        data = self._get_ppt(presentationid)
        # print(data["slides"][0])
        return_problem = []
        os.makedirs(os.path.join("output", presentationid),exist_ok=True)
        for idx, slide in enumerate(data["slides"]):
            if "cover" in slide.keys() and not os.path.exists(os.path.join("output", presentationid,"%s.jpg" % idx)):
                r = requests.get(slide["cover"],headers=self.headers,proxies={"http": None,"https":None})
                if r.status_code == 200:
                    with open(os.path.join("output", presentationid,"%s.jpg" % idx),"wb") as f:
                        f.write(r.content)
                        self.add_message("下载图片成功，路径为：%s" % os.path.join("output", presentationid,"%s.jpg" % idx),0)
                else:
                    self.add_message("下载图片失败，状态码：%s，路径为：%s" % (r.status_code,os.path.join("output", presentationid,"%s.jpg" % idx)),4)

            if "problem" in slide.keys():
                # replace with abs path
                # print(slide["problem"])
                local_path = os.path.join(os.path.abspath("output"), presentationid,"%s.jpg" % idx)
                slide["problem"]["image"] = local_path
                slide["problem"]["page"] = idx
                print(slide["problem"]["result"])
                return_problem.append(slide["problem"])
        return return_problem

    def answer_questions(self,problemid,problemtype,answer,limit):
        # 回答问题
        if answer:
            wait_time = calculate_waittime(limit, self.config["answer_config"]["answer_delay"]["type"], self.config["answer_config"]["answer_delay"]["custom"]["time"])
            if wait_time != 0:
                meg = "%s检测到问题，将在%s秒后自动回答，答案为%s" % (self.lessonname,wait_time,answer)
                self.add_message(meg,0)
                time.sleep(wait_time)
            else:
                meg = "%s检测到问题，剩余时间小于15秒，将立即自动回答，答案为%s" % (self.lessonname,answer)
                self.add_message(meg,0)
            data = {"problemId":problemid,"problemType":problemtype,"dt":int(time.time()),"result":answer}
            r = requests.post(url="https://pro.yuketang.cn/api/v3/lesson/problem/answer",headers=self.headers,data=json.dumps(data),proxies={"http": None,"https":None})
            return_dict = dict_result(r.text)
            if return_dict["code"] == 0:
                meg = "%s自动回答成功" % self.lessonname
                self.add_message(meg,0)
                return True
            else:
                meg = "%s自动回答失败，原因：%s" % (self.lessonname,return_dict["msg"].replace("_"," "))
                self.add_message(meg,4)
                return False
        else:
            if limit == -1:
                meg = "%s的问题没有找到答案，该题不限时，请尽快前往荷塘雨课堂回答" % (self.lessonname)
            else:
                meg = "%s的问题没有找到答案，请在%s秒内前往荷塘雨课堂回答" % (self.lessonname,limit)
            self.add_message(meg,4)
            return False
    
    def on_open(self, wsapp):
        self.handshake = {"op":"hello","userid":self.user_uid,"role":"student","auth":self.auth,"lessonid":self.lessonid}
        wsapp.send(json.dumps(self.handshake))

    def checkin_class(self):
        r = requests.post(url="https://pro.yuketang.cn/api/v3/lesson/checkin",headers=self.headers,data=json.dumps({"source":5,"lessonId":self.lessonid}),proxies={"http": None,"https":None})
        set_auth = r.headers.get("Set-Auth",None)
        times = 1
        while not set_auth and times <= 3:
            set_auth = r.headers.get("Set-Auth",None)
            times += 1
            time.sleep(1)
        self.headers["Authorization"] = "Bearer %s" % set_auth
        return dict_result(r.text)["data"]["lessonToken"]

    def on_message(self, wsapp, message):
        data = dict_result(message)
        op = data["op"]
        if op == "hello":
            presentations = list(set([slide["pres"] for slide in data["timeline"] if slide["type"]=="slide"]))
            current_presentation = data["presentation"]
            if current_presentation not in presentations:
                presentations.append(current_presentation)
            for presentationid in presentations:
                problems = self.get_problems(presentationid)
                for problem in problems:
                    for problem_exist in self.problems_ls:
                        if problem_exist["problemId"] == problem["problemId"]:
                            break
                    else:
                        self.problems_ls.append(problem)
                # self.problems_ls.extend(problems)
            self.unlocked_problem = data["unlockedproblem"]
            for problemid in self.unlocked_problem:
                self._current_problem(wsapp, problemid)
        elif op == "unlockproblem":
            self.start_answer(data["problem"]["sid"],data["problem"]["limit"])
        elif op == "lessonfinished":
            meg = "%s下课了" % self.lessonname
            self.add_message(meg,0)
            wsapp.close()
        elif op == "presentationupdated":
            # self.problems_ls.extend(self.get_problems(data["presentation"]))
            problems = self.get_problems(data["presentation"])
            for problem in problems:
                for problem_exist in self.problems_ls:
                    if problem_exist["problemId"] == problem["problemId"]:
                        break
                else:
                    self.problems_ls.append(problem)
        elif op == "presentationcreated":
            problems = self.get_problems(data["presentation"])
            for problem in problems:
                for problem_exist in self.problems_ls:
                    if problem_exist["problemId"] == problem["problemId"]:
                        break
                else:
                    self.problems_ls.append(problem)
        elif op == "newdanmu" and self.config["auto_danmu"]:
            current_content = data["danmu"].lower()
            uid = data["userid"]
            sent_danmu_user = User(uid)
            if sent_danmu_user in self.classmates_ls:
                for i in self.classmates_ls:
                    if i == sent_danmu_user:
                        meg = "%s课程的%s%s发送了弹幕：%s" %(self.lessonname,i.sno,i.name,data["danmu"])
                        self.add_message(meg,2)
                        break
            else:
                self.classmates_ls.append(sent_danmu_user)
                sent_danmu_user.get_userinfo(self.classroomid,self.headers)
                meg = "%s课程的%s%s发送了弹幕：%s" %(self.lessonname,sent_danmu_user.sno,sent_danmu_user.name,data["danmu"])
                self.add_message(meg,2)
            now = time.time()
            # 收到一条弹幕，尝试取出其之前的所有记录的列表，取不到则初始化该内容列表
            try:
                same_content_ls = self.danmu_dict[current_content]
            except KeyError:
                self.danmu_dict[current_content] = []
                same_content_ls = self.danmu_dict[current_content]
            # 清除超过60秒的弹幕记录
            for i in same_content_ls:
                if now - i > 60:
                    same_content_ls.remove(i)
            # 如果当前的弹幕没被发过，或者已发送时间超过60秒
            if current_content not in self.sent_danmu_dict.keys() or now - self.sent_danmu_dict[current_content] > 60:
                if len(same_content_ls) + 1 >= self.config["danmu_config"]["danmu_limit"]:
                    self.send_danmu(current_content)
                    same_content_ls = []
                    self.sent_danmu_dict[current_content] = now
                else:
                    same_content_ls.append(now)
        elif op == "callpaused":
            meg = "%s点名了，点到了：%s" % (self.lessonname, data["name"])
            if self.user_uname == data["name"]:
                self.add_message(meg,5)
            else:
                self.add_message(meg,6)
        # 程序在上课中途运行，由_current_problem发送的已解锁题目数据，得到的返回值。
        # 此处需要筛选未到期的题目进行回答。
        elif op == "probleminfo":
            if data["limit"] != -1:
                time_left = int(data["limit"]-(int(data["now"]) - int(data["dt"]))/1000)
            else:
                time_left = data["limit"]
            # 筛选未到期题目
            if time_left > 0 or time_left == -1:
                if self.config["auto_answer"]:
                    self.start_answer(data["problemid"],time_left)
                else:
                    if time_left == -1:
                        meg = "%s检测到问题，该题不限时，请尽快前往荷塘雨课堂回答" % (self.lessonname)
                        self.add_message(meg,0)
                    else:
                        meg = "%s检测到问题，请在%s秒内前往荷塘雨课堂回答" % (self.lessonname,time_left)

    def start_answer(self, problemid, limit):
        for promblem in self.problems_ls:
            if promblem["problemId"] == problemid:
                if promblem["result"] is not None:
                    # 如果该题已经作答过，直接跳出函数以忽略该题
                    # 该情况理论上只会出现在启动监听时
                    return
                # blanks = promblem.get("blanks",[])
                # answers = []
                answers = promblem.get("answers",[])
                if promblem["problemType"] == 5:
                    answers = {"content": answers[0], "pics": []}
                threading.Thread(target=self.answer_questions,args=(promblem["problemId"],promblem["problemType"],answers,limit)).start()
                # print("Try answer")
                break
        else:
            if limit == -1:
                meg = "%s的问题没有找到答案，该题不限时，请尽快前往荷塘雨课堂回答" % (self.lessonname)
            else:
                meg = "%s的问题没有找到答案，请在%s秒内前往荷塘雨课堂回答" % (self.lessonname,limit)
            self.add_message(meg,0)

    
    def _current_problem(self, wsapp, promblemid):
        # 为获取已解锁的问题详情信息，向wsapp发送probleminfo
        query_problem = {"op":"probleminfo","lessonid":self.lessonid,"problemid":promblemid,"msgid":1}
        wsapp.send(json.dumps(query_problem))
    
    def start_lesson(self, callback):
        self.auth = self.checkin_class()
        # 在tkinter中，我们不需要手动添加课程到表格，因为main_ui的update_course_table方法会自动处理
        self.wsapp = websocket.WebSocketApp(url=wss_url,header=self.headers,on_open=self.on_open,on_message=self.on_message)
        self.wsapp.run_forever()
        meg = "%s监听结束" % self.lessonname
        self.add_message(meg,0)
        return callback(self)
    
    def send_danmu(self,content):
        url = "https://pro.yuketang.cn/api/v3/lesson/danmu/send"
        data = {
            "extra": "",
            "fromStart": "50",
            "lessonId": self.lessonid,
            "message": content,
            "requiredCensor": False,
            "showStatus": True,
            "target": "",
            "userName": "",
            "wordCloud": True
        }
        r = requests.post(url=url,headers=self.headers,data=json.dumps(data),proxies={"http": None,"https":None})
        if dict_result(r.text)["code"] == 0:
            meg = "%s弹幕发送成功！内容：%s" % (self.lessonname,content)
        else:
            meg = "%s弹幕发送失败！内容：%s" % (self.lessonname,content)
        self.add_message(meg,0)
    
    def get_lesson_info(self):
        url = "https://pro.yuketang.cn/api/v3/lesson/basic-info"
        r = requests.get(url=url,headers=self.headers,proxies={"http": None,"https":None})
        return dict_result(r.text)["data"]
        

    def __eq__(self, other):
        return self.lessonid == other.lessonid

class User:
    def __init__(self, uid):
        self.uid = uid
    
    def get_userinfo(self, classroomid, headers):
        r = requests.get("https://pro.yuketang.cn/v/course_meta/fetch_user_info_new?query_user_id=%s&classroom_id=%s" % (self.uid,classroomid),headers=headers,proxies={"http": None,"https":None})
        data = dict_result(r.text)["data"]
        self.sno = data["school_number"]
        self.name = data["name"]