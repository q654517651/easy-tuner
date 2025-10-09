"""
最小TensorBoard Protobuf定义 - 动态构建所需类型
"""

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.descriptor import FieldDescriptor
from typing import Dict, Any, Optional


class TensorBoardProtoParser:
    """TensorBoard Protobuf解析器"""

    def __init__(self):
        self._event_class = None
        self._setup_classes()

    def _setup_classes(self):
        """设置protobuf类"""
        try:
            # 创建protobuf源码定义
            proto_src = '''
syntax = "proto3";

message Value {
  string tag = 1;
  float simple_value = 2;
}

message Summary {
  repeated Value value = 1;
}

message Event {
  double wall_time = 1;
  int64 step = 2;
  Summary summary = 5;
}
'''

            # 使用更简单的方法：直接创建描述符
            pool = descriptor_pool.Default()

            # 手动创建Event类
            self._create_simple_event_class()

        except Exception as e:
            from backend.app.utils.logger import log_error
            log_error("创建protobuf类失败", exc=e)
            self._event_class = None

    def _create_simple_event_class(self):
        """创建简化的Event类用于解析"""
        # 使用更简单的方法：创建一个基础的解析器
        class SimpleEvent:
            def __init__(self):
                self.wall_time = 0.0
                self.step = 0
                self.summary = None

            def ParseFromString(self, data):
                # 简化版解析 - 尝试解析基本字段
                import struct
                pos = 0
                while pos < len(data):
                    if pos + 1 >= len(data):
                        break

                    # 读取tag和wire type
                    tag_wire = data[pos]
                    pos += 1

                    field_num = tag_wire >> 3
                    wire_type = tag_wire & 0x07

                    if wire_type == 1:  # fixed64 (double)
                        if pos + 8 <= len(data):
                            if field_num == 1:  # wall_time
                                self.wall_time = struct.unpack('<d', data[pos:pos+8])[0]
                            pos += 8
                        else:
                            break
                    elif wire_type == 0:  # varint (int64)
                        value, pos = self._read_varint(data, pos)
                        if field_num == 2:  # step
                            self.step = value
                    elif wire_type == 2:  # length-delimited (string/bytes/message)
                        length, pos = self._read_varint(data, pos)
                        if pos + length <= len(data):
                            if field_num == 5:  # summary
                                summary_data = data[pos:pos+length]
                                self.summary = self._parse_summary(summary_data)
                            pos += length
                        else:
                            break
                    else:
                        # 跳过未知字段
                        pos += 1

            def _read_varint(self, data, pos):
                """读取varint编码的整数"""
                result = 0
                shift = 0
                while pos < len(data):
                    byte = data[pos]
                    pos += 1
                    result |= (byte & 0x7F) << shift
                    if (byte & 0x80) == 0:
                        break
                    shift += 7
                return result, pos

            def _parse_summary(self, data):
                """解析Summary消息"""
                class SimpleSummary:
                    def __init__(self):
                        self.value = []

                summary = SimpleSummary()
                pos = 0

                while pos < len(data):
                    if pos + 1 >= len(data):
                        break

                    tag_wire = data[pos]
                    pos += 1

                    field_num = tag_wire >> 3
                    wire_type = tag_wire & 0x07

                    if wire_type == 2 and field_num == 1:  # repeated Value
                        length, pos = self._read_varint(data, pos)
                        if pos + length <= len(data):
                            value_data = data[pos:pos+length]
                            value = self._parse_value(value_data)
                            if value:
                                summary.value.append(value)
                            pos += length
                        else:
                            break
                    else:
                        pos += 1

                return summary

            def _parse_value(self, data):
                """解析Value消息"""
                class SimpleValue:
                    def __init__(self):
                        self.tag = ""
                        self.simple_value = 0.0

                value = SimpleValue()
                pos = 0

                while pos < len(data):
                    if pos + 1 >= len(data):
                        break

                    tag_wire = data[pos]
                    pos += 1

                    field_num = tag_wire >> 3
                    wire_type = tag_wire & 0x07

                    if wire_type == 2 and field_num == 1:  # tag (string)
                        length, pos = self._read_varint(data, pos)
                        if pos + length <= len(data):
                            value.tag = data[pos:pos+length].decode('utf-8', errors='ignore')
                            pos += length
                        else:
                            break
                    elif wire_type == 5 and field_num == 2:  # simple_value (float)
                        if pos + 4 <= len(data):
                            import struct
                            value.simple_value = struct.unpack('<f', data[pos:pos+4])[0]
                            pos += 4
                        else:
                            break
                    else:
                        pos += 1

                return value if value.tag else None

            def HasField(self, field_name):
                return hasattr(self, field_name) and getattr(self, field_name) is not None

        self._event_class = SimpleEvent

    def parse_event(self, payload: bytes) -> Optional[Dict[str, Any]]:
        """解析事件protobuf数据"""
        if not self._event_class:
            return None

        try:
            # 解析事件消息
            event = self._event_class()
            event.ParseFromString(payload)

            # 检查是否有summary
            if not hasattr(event, 'summary') or not event.HasField('summary'):
                return None

            # 提取标量值
            scalars = []
            summary = event.summary
            if hasattr(summary, 'value'):
                for value in summary.value:
                    if hasattr(value, 'simple_value') and hasattr(value, 'tag'):
                        scalars.append({
                            'tag': value.tag,
                            'value': float(value.simple_value)
                        })

            if not scalars:
                return None

            return {
                'wall_time': float(event.wall_time) if hasattr(event, 'wall_time') else 0.0,
                'step': int(event.step) if hasattr(event, 'step') else 0,
                'scalars': scalars
            }

        except Exception as e:
            # 静默忽略解析错误（可能是其他类型的事件）
            return None


# 全局解析器实例
_parser_instance = None


def get_proto_parser() -> TensorBoardProtoParser:
    """获取全局protobuf解析器实例"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = TensorBoardProtoParser()
    return _parser_instance
