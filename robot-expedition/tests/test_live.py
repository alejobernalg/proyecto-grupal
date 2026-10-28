import json
import socket

from websockets.sync.client import connect

from robot_expedition.envs import RobotExpeditionEnv
from robot_expedition.export.episode import EpisodeRecorder
from robot_expedition.export.live import LiveServer


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def test_live_server_sends_episode_then_frames(config, tmp_path):
    env = EpisodeRecorder(RobotExpeditionEnv(config), out_dir=tmp_path, auto_save=False)
    env.reset(seed=0)
    env.step(0)  # el visor se conecta a mitad de partida
    server = LiveServer(env.to_dict, port=free_port())
    try:
        with connect(server.url) as ws:
            hello = json.loads(ws.recv(timeout=5))
            assert hello["type"] == "episode"
            assert len(hello["episode"]["frames"]) == 2
            assert hello["episode"]["map"]["size"] == 12

            env.step(2)
            server.send_frame(env.frames[-1])
            message = json.loads(ws.recv(timeout=5))
            assert message["type"] == "frame"
            assert message["frame"]["step"] == 2
            assert message["frame"]["robot"]["orientation"] == "E"
    finally:
        server.close()
