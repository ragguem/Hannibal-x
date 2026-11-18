"""Monde LOTUSim par ROS 2 : couche anti-corruption entre `lotusim_msgs` et le vocabulaire Hannibal.

Repris du nœud `hannibal_server_v3` de legacy/app_v3/server.py (`Ros.on_poses`, `Ros.send`, `Ros.spawn`,
`Ros.delete`, envoi `SetWaypoints`). `rclpy` et les messages ne sont importés qu'au démarrage : ce module se
charge, et ses conversions se testent, sans ROS. LOTUSim oriente le lacet depuis l'est dans le sens direct ;
Hannibal compte le cap depuis le nord dans le sens horaire.
"""

import asyncio
import math
import threading
import time
from collections.abc import Mapping
from typing import Any

from hannibal_platform.logging import get_logger
from hannibal_sim_bridge.world import WorldUnavailable

log = get_logger(__name__)

VESSEL_SDF = (
    "<lotus_param><render_interface><publish_render>true</publish_render><renderer_type_name>fremm"
    "</renderer_type_name></render_interface><waypoint_follower><follower><loop>false</loop>"
    "<range_tolerance>1</range_tolerance><line><direction>0</direction><length>5000</length></line>"
    "<linear_velocities_limits>0.5 16</linear_velocities_limits><linear_accel_limit>0.8</linear_accel_limit>"
    "<angular_velocities_limits>0.07</angular_velocities_limits><angular_accel_limit>0.03</angular_accel_limit>"
    "</follower></waypoint_follower></lotus_param>"
)


def heading_from_quaternion(x: float, y: float, z: float, w: float) -> float:
    yaw_deg = math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
    heading = (90.0 - yaw_deg) % 360.0
    return 0.0 if heading >= 360.0 else heading


def quaternion_z_w_from_heading(heading_deg: float) -> tuple[float, float]:
    yaw = math.radians(90.0 - heading_deg)
    return math.sin(yaw / 2), math.cos(yaw / 2)


def ship_state(vessel: Any) -> dict[str, float]:
    """`lotusim_msgs/VesselPosition` -> état Hannibal (mêmes clés que `Ros.st` de l'ancien serveur)."""
    q = vessel.pose.orientation
    return {
        "x": float(vessel.pose.position.x),
        "y": float(vessel.pose.position.y),
        "lat": float(vessel.geo_point.latitude),
        "lon": float(vessel.geo_point.longitude),
        "sog": float(vessel.speed_over_ground),
        "hdg": heading_from_quaternion(q.x, q.y, q.z, q.w),
    }


class RosWorld:
    def __init__(self, world_name: str, model_name: str, command_timeout_s: float) -> None:
        self._world_name = world_name
        self._model_name = model_name
        self._timeout_s = command_timeout_s
        self._lock = threading.RLock()
        self._states: dict[str, dict[str, float]] = {}
        self._waypoint_clients: dict[str, Any] = {}
        self._node: Any = None
        self._executor: Any = None
        self._spin_thread: threading.Thread | None = None
        self._ros: Any = None

    async def start(self) -> None:
        import rclpy
        from geographic_msgs.msg import GeoPoint
        from geometry_msgs.msg import Pose
        from lotusim_msgs.action import MASCmdArray
        from lotusim_msgs.msg import MASCmd, VesselPositionArray
        from lotusim_msgs.srv import SetWaypoints
        from rclpy.action import ActionClient
        from rclpy.executors import SingleThreadedExecutor

        self._ros = {
            "GeoPoint": GeoPoint,
            "Pose": Pose,
            "MASCmd": MASCmd,
            "MASCmdArray": MASCmdArray,
            "SetWaypoints": SetWaypoints,
        }
        rclpy.init()
        self._node = rclpy.create_node("hannibal_sim_bridge", namespace="/lotusim")
        self._node.create_subscription(VesselPositionArray, f"/{self._world_name}/poses", self._on_poses, 10)
        self._commands = ActionClient(self._node, MASCmdArray, f"/{self._world_name}/mas_cmd_array")
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(target=self._executor.spin, name="ros-spin", daemon=True)
        self._spin_thread.start()
        log.info("ros_world_started", world=self._world_name)

    async def stop(self) -> None:
        import rclpy

        if self._executor is not None:
            self._executor.shutdown()
        if self._node is not None:
            self._node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    def _on_poses(self, message: Any) -> None:
        with self._lock:
            for vessel in message.vessels:
                self._states[vessel.vessel_name] = ship_state(vessel)

    def _send_commands(self, commands: list[Any], timeout_s: float) -> None:
        goal = self._ros["MASCmdArray"].Goal()
        goal.cmd.extend(commands)
        if not self._commands.wait_for_server(timeout_sec=timeout_s):
            raise WorldUnavailable("action mas_cmd_array indisponible")
        accepted = threading.Event()
        box: dict[str, Any] = {}

        def on_goal(future: Any) -> None:
            box["handle"] = future.result()
            accepted.set()

        self._commands.send_goal_async(goal).add_done_callback(on_goal)
        if not accepted.wait(timeout_s) or not box.get("handle") or not box["handle"].accepted:
            raise WorldUnavailable("commande MASCmdArray refusée ou sans réponse")
        done = threading.Event()
        box["handle"].get_result_async().add_done_callback(lambda _: done.set())
        if not done.wait(timeout_s):
            raise WorldUnavailable("commande MASCmdArray sans résultat")

    def _delete_commands(self, names: list[str]) -> list[Any]:
        mas_cmd = self._ros["MASCmd"]
        commands = []
        for name in names:
            command = mas_cmd()
            command.cmd_type = mas_cmd.DELETE_CMD
            command.vessel_name = name
            commands.append(command)
        return commands

    def _create_commands(self, ships: Mapping[str, tuple[float, float, float]]) -> list[Any]:
        mas_cmd, pose_type = self._ros["MASCmd"], self._ros["Pose"]
        commands = []
        for name, (east_m, north_m, heading_deg) in ships.items():
            command = mas_cmd()
            command.cmd_type = mas_cmd.CREATE_CMD
            command.model_name = self._model_name
            command.vessel_name = name
            command.vessel_position = pose_type()
            command.vessel_position.position.x = float(east_m)
            command.vessel_position.position.y = float(north_m)
            z, w = quaternion_z_w_from_heading(heading_deg)
            command.vessel_position.orientation.z = z
            command.vessel_position.orientation.w = w
            command.sdf_string = VESSEL_SDF
            commands.append(command)
        return commands

    def _replace_fleet(self, ships: Mapping[str, tuple[float, float, float]]) -> None:
        with self._lock:
            present = list(self._states)
            self._states.clear()
            self._waypoint_clients.clear()
        if present:
            self._send_commands(self._delete_commands(present), min(self._timeout_s, 8.0))
        if ships:
            self._send_commands(self._create_commands(ships), self._timeout_s)

    async def spawn(self, ships: Mapping[str, tuple[float, float, float]]) -> None:
        await asyncio.to_thread(self._replace_fleet, dict(ships))

    async def clear(self) -> None:
        await asyncio.to_thread(self._replace_fleet, {})

    async def states(self) -> dict[str, dict[str, float]]:
        with self._lock:
            return {name: dict(state) for name, state in self._states.items()}

    def _waypoint_client(self, name: str) -> Any:
        client = self._waypoint_clients.get(name)
        if client is None:
            service = f"/{self._world_name}/{name}/waypoints"
            if any(found == service for found, _ in self._node.get_service_names_and_types()):
                client = self._node.create_client(self._ros["SetWaypoints"], service)
                self._waypoint_clients[name] = client
        return client

    async def steer(self, waypoints: Mapping[str, tuple[float, float]]) -> None:
        started = time.perf_counter()
        for name, (lat, lon) in waypoints.items():
            client = self._waypoint_client(name)
            if client is None:
                continue
            request = self._ros["SetWaypoints"].Request()
            request.loop = False
            request.path = [self._ros["GeoPoint"](latitude=lat, longitude=lon, altitude=0.0)]
            client.call_async(request)
        log.debug("waypoints_sent", ships=len(waypoints), ms=round((time.perf_counter() - started) * 1000, 1))
