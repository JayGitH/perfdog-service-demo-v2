# coding: utf-8

import logging
import time
import subprocess
import threading
import grpc
import perfdog_pb2
import perfdog_pb2_grpc


class Stream(object):
    def __init__(self, stream, callback):
        self.__steam = stream
        self.__callback = callback
        t = threading.Thread(target=self.__run)
        t.setDaemon(True)
        t.start()

    def __run(self):
        try:
            for data in self.__steam:
                self.__callback(data)
        except Exception as e:
            logging.info(e)

    def stop(self):
        self.__steam.cancel()


class Service(object):
    def __init__(self, service_token, service_path, service_wait_seconds=10):
        try:
            self.__stub_factory = self.__create_stub_factory()
            self.__login(service_token)
        except:
            self.__startup(service_path, service_wait_seconds)
            self.__stub_factory = self.__create_stub_factory()
            self.__login(service_token)

    @staticmethod
    def __startup(service_path, service_wait_seconds):
        subprocess.Popen(service_path)
        time.sleep(service_wait_seconds)

    @staticmethod
    def __create_stub_factory():
        channel = grpc.insecure_channel('127.0.0.1:23456',
                                        options=[('grpc.max_receive_message_length', 100 * 1024 * 1024)])
        return lambda: perfdog_pb2_grpc.PerfDogServiceStub(channel)

    def __login(self, service_token):
        user_info = self.stub().loginWithToken(perfdog_pb2.Token(token=service_token))
        logging.info("UserInfo: \n%s", user_info)

    def stub_factory(self):
        return self.__stub_factory

    def stub(self):
        return self.__stub_factory()

    def get_devices(self):
        req = perfdog_pb2.Empty()
        res = self.stub().getDeviceList(req)
        return [Device(device, self.__stub_factory) for device in res.devices]

    def get_device(self, device_id, conn_type):
        for device in self.get_devices():
            if device.uid() == device_id and device.conn_type() == conn_type:
                return device

    def get_usb_device(self, device_id):
        return self.get_device(device_id, perfdog_pb2.USB)

    def get_wifi_device(self, device_id):
        return self.get_device(device_id, perfdog_pb2.WIFI)

    def get_device_event_stream(self, callback):
        return Stream(self.stub().startDeviceMonitor(perfdog_pb2.Empty()), callback)

    def set_global_data_upload_server(self, url, data_format):
        req = perfdog_pb2.SetDataUploadServerReq(serverUrl=url, dataUploadFormat=data_format)
        self.stub().setGlobalDataUploadServer(req)

    def clear_global_data_upload_server(self):
        req = perfdog_pb2.SetDataUploadServerReq(serverUrl='')
        self.stub().setGlobalDataUploadServer(req)

    def disable_install_apk(self):
        preferences = perfdog_pb2.Preferences(doNotInstallPerfDogApp=True)
        req = perfdog_pb2.SetPreferencesReq(preferences=preferences)
        self.stub().setPreferences(req)

    def enable_install_apk(self):
        preferences = perfdog_pb2.Preferences(doNotInstallPerfDogApp=False)
        req = perfdog_pb2.SetPreferencesReq(preferences=preferences)
        self.stub().setPreferences(req)

    def create_task(self, task_name):
        req = perfdog_pb2.CreateTaskReq(taskName=task_name)
        res = self.stub().createTask(req)
        return res.taskId

    def archive_case_to_task(self, task_id, case_id):
        req = perfdog_pb2.ArchiveCaseToTaskReq(caseId=case_id, taskId=task_id)
        self.stub().archiveCaseToTask(req)

    def share_case(self, case_id, expire_time, non_password=False):
        req = perfdog_pb2.ShareCaseReq(caseId=case_id, expireTime=expire_time, nonPassword=non_password)
        return self.stub().shareCase(req)

    def kill_server(self):
        req = perfdog_pb2.Empty()
        self.stub().killServer(req)


class Device(object):
    def __init__(self, real_device, stub_factory):
        self.__real_device = real_device
        self.__stub_factory = stub_factory

    def real_device(self):
        return self.__real_device

    def stub_factory(self):
        return self.__stub_factory

    def stub(self):
        return self.__stub_factory()

    def uid(self):
        return self.__real_device.uid

    def name(self):
        return self.__real_device.name

    def os_type(self):
        return self.__real_device.osType

    def conn_type(self):
        return self.__real_device.conType

    def __repr__(self):
        return self.__display_str()

    def __str__(self):
        return self.__display_str()

    def __display_str(self):
        conn_type = 'USB' if self.__real_device.conType == perfdog_pb2.USB else 'WIFI'
        os_type = 'iOS' if self.__real_device.osType == perfdog_pb2.IOS else 'Android'
        return '{{uid: {}, name: {}, conn_type: {}, os_type: {}}}'.format(self.__real_device.uid,
                                                                          self.__real_device.name,
                                                                          conn_type,
                                                                          os_type
                                                                          )

    def init(self):
        self.stub().initDevice(self.__real_device)

    def get_info(self):
        return self.stub().getDeviceInfo(self.__real_device)

    def get_status(self):
        return self.stub().getDeviceStatus(self.__real_device)

    def get_apps(self):
        res = self.stub().getAppList(self.__real_device)
        return res.app

    def get_app(self, package_name):
        apps = self.get_apps()
        for app in apps:
            if app.packageName == package_name:
                return app
        return None

    def get_app_running_processes(self, app):
        req = perfdog_pb2.GetAppRunningProcessReq(device=self.__real_device, app=app)
        res = self.stub().getAppRunningProcess(req)
        return res.processInfo

    def get_app_windows_map(self, app):
        req = perfdog_pb2.GetAppWindowsMapReq(device=self.__real_device, app=app)
        res = self.stub().getAppWindowsMap(req)
        return res.pid2WindowMap

    def get_sys_processes(self):
        res = self.stub().getRunningSysProcess(self.__real_device)
        return res.processInfo

    def get_available_types(self):
        res = self.stub().getAvailableDataType(self.__real_device)
        return res.type

    def get_types(self):
        res = self.stub().getPerfDataType(self.__real_device)
        return res.type

    def enable_types(self, *types):
        for ty in types:
            req = perfdog_pb2.EnablePerfDataTypeReq(device=self.__real_device, type=ty)
            self.stub().enablePerfDataType(req)

    def disable_types(self, *types):
        for ty in types:
            req = perfdog_pb2.DisablePerfDataTypeReq(device=self.__real_device, type=ty)
            self.stub().disablePerfDataType(req)

    def set_screenshot_interval(self, seconds):
        req = perfdog_pb2.ScreenShotInterval(device=self.__real_device, second=seconds)
        self.stub().setScreenShotInterval(req)

    def start_test_app(self, req):
        self.stub().startTestApp(req)

    def start_test_sys_process(self, req):
        self.stub().startTestSysProcess(req)

    def stop_test(self):
        req = perfdog_pb2.StopTestReq(device=self.__real_device)
        self.stub().stopTest(req)

    def get_perf_data_stream(self, callback):
        req = perfdog_pb2.OpenPerfDataStreamReq(device=self.__real_device)
        return Stream(self.stub().openPerfDataStream(req), callback)

    def save_data(self,
                  begin_time=None,
                  end_time=None,
                  case_name=None,
                  is_upload=True,
                  is_export=False,
                  export_format=perfdog_pb2.EXPORT_TO_EXCEL,
                  export_directory=''):
        req = perfdog_pb2.SaveDataReq(
            device=self.__real_device,
            beginTime=begin_time,
            endTime=end_time,
            caseName=case_name,
            uploadToServer=is_upload,
            exportToFile=is_export,
            dataExportFormat=export_format,
            outputDirectory=export_directory,
        )
        return self.stub().saveData(req)

    def set_label(self, label_name):
        req = perfdog_pb2.SetLabelReq(device=self.__real_device, label=label_name)
        return self.stub().setLabel(req)

    def add_note(self, note_name, note_time):
        req = perfdog_pb2.AddNoteReq(device=self.__real_device, time=note_time, note=note_name)
        self.stub().addNote(req)

    def get_cache_stream(self, callback):
        req = perfdog_pb2.GetDeviceCacheDataReq(device=self.__real_device)
        return Stream(self.stub().getDeviceCacheData(req), callback)

    def get_cache_packed_stream(self, callback, data_format=perfdog_pb2.JSON):
        req = perfdog_pb2.GetDeviceCacheDataPackedReq(device=self.__real_device, dataFormat=data_format)
        return Stream(self.stub().getDeviceCacheDataPacked(req), callback)


class NotSetTestTarget(Exception):
    pass


class NonExistTestTarget(Exception):
    pass


class TestTarget(object):
    def __init__(self, is_app, req):
        self.__is_app = is_app
        self.__req = req

    def is_app(self):
        return self.__is_app

    def req(self):
        return self.__req


class TestTargetBuilder(object):
    def __init__(self, device):
        self.__device = device

    def device(self):
        return self.__device


class TestAppBuilder(TestTargetBuilder):
    def __init__(self, device):
        super().__init__(device)
        self.__package_name = None
        self.__sub_process_name = None
        self.__hide_floating_window = False
        self.__sub_window = None

    def set_package_name(self, package_name):
        self.__package_name = package_name

    def set_sub_process_name(self, sub_process_name):
        self.__sub_process_name = sub_process_name

    def hide_floating_window(self):
        self.__hide_floating_window = True

    def show_floating_window(self):
        self.__hide_floating_window = False

    def set_sub_window(self, sub_window):
        self.__sub_window = sub_window

    def build(self):
        app = self.device().get_app(self.__package_name)
        if app is None:
            raise NonExistTestTarget()

        req = perfdog_pb2.StartTestAppReq(device=self.device().real_device(),
                                          app=app,
                                          subProcess=self.__sub_process_name,
                                          hideFloatingWindow=self.__hide_floating_window,
                                          subWindow=self.__sub_window,
                                          )
        return TestTarget(True, req)


class TestSysProcessBuilder(TestTargetBuilder):
    def __init__(self, device):
        super().__init__(device)
        self.__process_name = None
        self.__hide_floating_window = False

    def set_process_name(self, process_name):
        self.__process_name = process_name

    def hide_floating_window(self):
        self.__hide_floating_window = True

    def show_floating_window(self):
        self.__hide_floating_window = False

    def build(self):
        processes = self.device().get_sys_processes()
        process = None
        for v in processes:
            if v.name == self.__process_name:
                process = v
                break

        if process is None:
            raise NonExistTestTarget()

        req = perfdog_pb2.StartTestSysProcessReq(device=self.device().real_device(),
                                                 sysProcessInfo=process,
                                                 hideFloatingWindow=self.__hide_floating_window)
        return TestTarget(False, req)


class StreamPerfData(object):
    def __init__(self):
        #
        self.__stream = None

        #
        self.__has_first_perf_data = False
        self.__first_perf_data_callback = None

        #
        self.__perf_data_callback = None

    def set_first_perf_data_callback(self, first_perf_data_callback):
        self.__first_perf_data_callback = first_perf_data_callback

    def set_perf_data_callback(self, perf_data_callback):
        self.__perf_data_callback = perf_data_callback

    def start(self, create_stream):
        if self.__first_perf_data_callback is not None or self.__perf_data_callback is not None:
            self.__stream = create_stream(self.__handle_perf_data)

    def stop(self):
        if self.__stream is not None:
            self.__stream.stop()
            self.__stream = None

    def __handle_perf_data(self, perf_data):
        use_stream_count = 0
        use_stream_count += 1 if self.__handle_first_perf_data(perf_data) else 0
        if self.__perf_data_callback is not None:
            self.__perf_data_callback(perf_data)
            use_stream_count += 1

        if use_stream_count == 0:
            self.stop()

    def __handle_first_perf_data(self, perf_data):
        if self.__has_first_perf_data:
            return False

        if self.__is_fps_data(perf_data):
            self.__has_first_perf_data = True
            if self.__first_perf_data_callback is not None:
                self.__first_perf_data_callback()
            return False

        else:
            return True

    @staticmethod
    def __is_fps_data(perf_data):
        if perf_data.HasField('iosPerfData'):
            perf_data = perf_data.iosPerfData
        elif perf_data.HasField('androidPerfData'):
            perf_data = perf_data.androidPerfData
        else:
            return False

        if perf_data.HasField('fpsData'):
            return True
        else:
            return False


class Test(object):
    def __init__(self, device):
        #
        self.__device = device

        #
        device_status = self.__device.get_status()
        if device_status.isTesting:
            self.__device.stop_test()
        self.__device.init()

        #
        self.__available_types = self.__device.get_available_types()
        self.__enable_types = []
        self.__disable_types = []
        self.__test_target = None

        #
        self.__stream_perf_data = StreamPerfData()

    def set_first_perf_data_callback(self, first_perf_data_callback):
        self.__stream_perf_data.set_first_perf_data_callback(first_perf_data_callback)

    def set_perf_data_callback(self, perf_data_callback):
        self.__stream_perf_data.set_perf_data_callback(perf_data_callback)

    def create_test_target_builder(self, factory):
        return factory(self.__device)

    def set_test_target(self, test_target):
        self.__test_target = test_target

    def set_types(self, *types):
        for ty in self.__available_types:
            if ty in types:
                self.__enable_types.append(ty)
            else:
                self.__disable_types.append(ty)

    def enable_types(self, *types):
        self.__enable_types.extend(types)

    def disable_types(self, *types):
        self.__disable_types.extend(types)

    def start(self):
        if self.__test_target is None:
            raise NotSetTestTarget()

        # 启用和禁用相关性能指标
        self.__device.enable_types(*self.__enable_types)
        self.__device.disable_types(*self.__disable_types)

        # 开始测试
        if self.__test_target.is_app():
            self.__device.start_test_app(self.__test_target.req())
        else:
            self.__device.start_test_sys_process(self.__test_target.req())

        #
        self.__stream_perf_data.start(self.__device.get_perf_data_stream)

    def stop(self):
        self.__stream_perf_data.stop()
        self.__device.stop_test()

    def save_data(self,
                  begin_time=None,
                  end_time=None,
                  case_name=None,
                  is_upload=True,
                  is_export=False,
                  export_format=perfdog_pb2.EXPORT_TO_EXCEL,
                  export_directory=''):
        return self.__device.save_data(begin_time, end_time, case_name, is_upload, is_export, export_format,
                                       export_directory)

    def set_label(self, label_name):
        return self.__device.set_label(label_name)

    def add_note(self, note_name, note_time):
        return self.__device.add_note(note_name, note_time)
