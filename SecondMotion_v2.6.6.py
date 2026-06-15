"""
SecondMotion v2.6.6  (+ VertexMap : Surface Controller Builder)
──────────────────────────────────────────────────────────────────────────

[v2.6.6 Update]
  ■ 삭제 시 남은 항목이 없으면 비어 있는 상위 그룹(VertexMap_GRP, SecondMotion_GRP)도 함께 삭제

[v2.6.5 Update]
  ■ 삭제 연동: VertexMap 컨트롤(스피어/큐브)을 아웃라이너/뷰포트에서 직접 지워도
    연관 노드(JNT/OFFSET/CTRL/제약/holder/그룹)가 함께 정리되도록 노드 삭제 콜백 추가
    - 툴의 [Delete Selected]는 리스트 선택뿐 아니라 씬에서 선택한 컨트롤 기준으로도 삭제
  ■ 안내: 살(flesh)처럼 상하로 출렁이려면 Overlap 모드에서 Rotation이 아니라
    Translation(특히 Y축)을 켜야 함 (필요 시 Physics 병행). 메시지로 가이드 추가

[v2.6.4 Update]
  ■ Jiggle 베이크 수정: 컨스트레인트로 구동되는 컨트롤(VertexMap 등)의 월드 모션을
    getAttr(-time)이 정지로 읽어 lag가 0이 되던 문제 해결
    - 컨트롤/상위 노드가 컨스트레인트로 구동되면 타임라인을 스크럽하며 월드 모션을 정확히 샘플링
    - 일반 애님 커브 컨트롤은 기존 빠른 경로(getAttr -time) 그대로 유지
  → 이제 생성한 스피어를 선택하고 Overlap APPLY 하면 따라가는 몸의 움직임을 따라 출렁임이 베이크됨

[v2.6.3 Update]
  ■ 노드 정리: SecondMotion_GRP > VertexMap_GRP > <모델명>_VM_GRP 계층으로 묶어 정리
    - 각 생성 단위(JNT/OFFSET/CTRL/holder)가 자기 그룹 안에 들어감
  ■ Jiggle 연결: 생성된 컨트롤(OFFSET)이 해당 버텍스의 주된 리그 조인트를 따라가도록 구성
    - 몸이 애니메이션되면 컨트롤도 따라가고 → Overlap 탭에서 Apply 시 lag(스프링)가 베이크되어 출렁임 발생
    - 디포메이션된 메쉬가 아닌 리그 조인트를 추종하므로 순환 의존성(cycle) 없음

[v2.6.1 Update]
  ■ VertexMap 재설계: 두 모드 모두 '조인트 + 스킨 웨이트' 방식으로 통일
    - Soft(버텍스 1개) : 중심에서 둥글게 자동 폴오프 페인트 (소프트 셀렉션 방식)
    - Joint(버텍스 2개+): 조인트 N개 생성, Paint 버튼으로 직접 스킨 웨이트 페인트
  ■ Scale/Weight/Effect/Falloff 슬라이더가 선택된 컨트롤러에 '실시간' 반영
    - Scale  : 영향 반경 + 스피어 컨트롤 가시 크기(드래그 즉시) — 트랜스폼은 깨끗하게 유지
    - Weight : 중심 최대 가중치(릴리즈 시 둥근 폴오프 재페인트 + 컬러 피드백 갱신)
    - Effect : 폴오프 집중도, FalloffMode(Volume/Surface), FalloffCurve(Smooth/Spline/Linear/Flat)
  ■ 생성한 스피어 컨트롤을 Overlap 탭에서 선택 후 Apply → 지글(Jiggle) 베이크

[v2.6.0 Update]
  ■ 신규 탭 'VertexMap' 추가
    - 리깅 컨트롤러가 부족한 메쉬 표면에 지글(Jiggle)용 컨트롤러를 직접 생성
    - 생성 모드 1 (Soft / softMod) : 버텍스 1개 선택 → 소프트 셀렉션처럼 주변에 영향을 주는 컨트롤러
    - 생성 모드 2 (Joint / skin)   : 버텍스 2개 이상 선택 → 조인트형 컨트롤러 + 스킨 웨이트 직접 페인트
    - Shape(Cube/Sphere), Scale, Weight, Effect, FalloffMode(Surface/Volume),
      FalloffCurve(Spline/Smooth/Linear/Flat), Orient to World Space 커스텀
  ■ 탭 구성: Overlap / VertexMap / About

[v2.5.2 Update]
  ■ UI 편의성 개선: APPLY 버튼 바로 하단에 [DELETE CURRENT VertexMap LAYER] 버튼 추가
  ■ 피드백 반영: 삭제 완료 시 Warning 경고등 대신 깔끔한 InViewMessage 및 일반 Print로 변경
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.mel as mel
import math
import json
import os

CHANNELS     = ["rotateX", "rotateY", "rotateZ",
                "translateX", "translateY", "translateZ"]
ROT_CHANNELS = CHANNELS[:3]
TR_CHANNELS  = CHANNELS[3:]

ROT_ORDERS = [
    om.MEulerRotation.kXYZ, om.MEulerRotation.kYZX,
    om.MEulerRotation.kZXY, om.MEulerRotation.kXZY,
    om.MEulerRotation.kYXZ, om.MEulerRotation.kZYX,
]

class UserCancelled(Exception):
    pass

# ══════════════════════════════════════════════════════════════
#  PresetManager
# ══════════════════════════════════════════════════════════════
class PresetManager:
    DEFAULTS = {
        "Natural": {"soft": 3.0, "scale": 0.8, "smooth": 0.1, "decay": 1.0},
        "Heavy":   {"soft": 6.0, "scale": 0.4, "smooth": 0.3, "decay": 0.9},
        "Bouncy":  {"soft": 2.0, "scale": 0.9, "smooth": 0.05, "decay": 1.1},
        "Whip":    {"soft": 2.0, "scale": 0.7, "smooth": 0.05, "decay": 1.3},
        "Sharp":   {"soft": 1.0, "scale": 1.2, "smooth": 0.0, "decay": 1.0},
    }

    def __init__(self):
        self.path = os.path.join(
            cmds.internalVar(userAppDir=True), "scripts", "sm_presets.json"
        )

    def load(self):
        if not os.path.exists(self.path):
            self._write(dict(self.DEFAULTS))
            return dict(self.DEFAULTS)
        try:
            with open(self.path) as f:
                data = json.load(f)
            for v in data.values():
                v.setdefault("decay", 1.0)
            return data
        except Exception:
            return dict(self.DEFAULTS)

    def save(self, name, values):
        presets = self.load()
        presets[name] = values
        self._write(presets)

    def delete(self, name):
        if name in self.DEFAULTS:
            cmds.warning("Cannot delete default presets.")
            return False
        presets = self.load()
        if name in presets:
            del presets[name]
            self._write(presets)
            return True
        return False

    def get(self, name):
        return self.load().get(name)

    def _write(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=4)

# ══════════════════════════════════════════════════════════════
#  OverlapEngine
# ══════════════════════════════════════════════════════════════
class OverlapEngine:
    LAYER_PREFIX = "SM_"

    def __init__(self):
        pass

    @classmethod
    def layer_name_for(cls, root_ctrl):
        short = root_ctrl.rsplit("|", 1)[-1].replace(":", "_")
        return f"{cls.LAYER_PREFIX}{short}"

    @classmethod
    def list_sm_layers(cls):
        layers = cmds.ls(type="animLayer") or []
        return sorted(l for l in layers if l.startswith(cls.LAYER_PREFIX))

    @classmethod
    def delete_sm_layer(cls, layer):
        if layer and cmds.objExists(layer):
            cmds.delete(layer)
            return True
        return False

    @classmethod
    def delete_all_sm_layers(cls):
        count = 0
        for l in cls.list_sm_layers():
            cmds.delete(l)
            count += 1
        return count

    @classmethod
    def get_layer_weight(cls, layer):
        if layer and cmds.objExists(layer):
            try:
                return cmds.animLayer(layer, q=True, weight=True) * 100.0
            except Exception:
                pass
        return 100.0

    @classmethod
    def set_layer_weight(cls, layer, percent):
        if layer and cmds.objExists(layer):
            cmds.animLayer(layer, e=True, weight=percent / 100.0)

    def run(self, softness, scale, smoothing, decay,
            lock_rx, lock_ry, lock_rz,
            lock_tx, lock_ty, lock_tz,
            use_range, range_start, range_end,
            hier_mode, cycle_mode, ignore_first,
            layer_weight,
            wind_enable, wind_dir, wind_strength,
            custom_enable, custom_in, custom_out, custom_gain,
            physics_enable=False, overshoot=0.5):

        initial_sel = cmds.ls(selection=True, long=True)
        if not initial_sel:
            cmds.warning("Please select controllers first.")
            return None

        final_list = self._build_final_list(initial_sel, hier_mode, ignore_first)
        if not final_list:
            cmds.warning("No controllers to process.")
            return None

        start, end = self._resolve_range(use_range, range_start, range_end)
        if end <= start:
            cmds.warning("Invalid frame range.")
            return None

        delay = max(1, int(softness))
        locks = dict(zip(
            CHANNELS,
            [lock_rx, lock_ry, lock_rz, lock_tx, lock_ty, lock_tz],
        ))

        layer_name = self.layer_name_for(initial_sel[0])
        if cmds.objExists(layer_name):
            cmds.delete(layer_name)
        self._detach_from_other_layers(final_list, layer_name)
        self._ensure_layer(layer_name, final_list)

        cmds.undoInfo(openChunk=True)
        cmds.progressWindow(
            title="SecondMotion v2.6.6",
            status="Preparing...",
            progress=0, maxValue=100,
            isInterruptable=True,
        )
        ok = False
        try:
            self._bake_all(
                layer_name, initial_sel, final_list,
                start, end, delay, scale, smoothing, decay,
                locks, hier_mode, cycle_mode,
                wind_enable, wind_dir, wind_strength,
                custom_enable, custom_in, custom_out, custom_gain,
                physics_enable, overshoot
            )
            self.set_layer_weight(layer_name, layer_weight)
            ok = True
        except UserCancelled:
            cmds.warning("SecondMotion cancelled by user. (Ctrl+Z to undo)")
        except Exception as e:
            import traceback
            traceback.print_exc()
            cmds.warning(f"Overlap error: {e}")
        finally:
            cmds.progressWindow(endProgress=True)
            cmds.select(initial_sel, replace=True)
            cmds.undoInfo(closeChunk=True)

        return layer_name if ok else None

    def _detach_from_other_layers(self, ctrls, current_layer):
        prev_sel = cmds.ls(selection=True, long=True)
        try:
            cmds.select(ctrls, replace=True)
            affected = cmds.animLayer(q=True, affectedLayers=True) or []
            for lay in affected:
                if not lay.startswith(self.LAYER_PREFIX): continue
                if lay == current_layer: continue
                try: cmds.animLayer(lay, e=True, removeSelectedObjects=True)
                except: continue
                remaining = cmds.animLayer(lay, q=True, attribute=True)
                if not remaining: cmds.delete(lay)
        finally:
            if prev_sel: cmds.select(prev_sel, replace=True)
            else: cmds.select(clear=True)

    def _ensure_layer(self, layer_name, nodes):
        if not cmds.objExists(layer_name):
            cmds.animLayer(layer_name)
        usable = [
            n for n in nodes
            if not all(self._channel_blocked(n, ch) for ch in CHANNELS)
        ]
        if usable:
            cmds.select(usable, replace=True)
            cmds.animLayer(layer_name, e=True, addSelectedObjects=True)

    def _build_final_list(self, initial_sel, hier_mode, ignore_first):
        sel = list(initial_sel)
        if ignore_first and sel:
            first = sel[0]
            sel   = sel[1:]
            if not sel and hier_mode:
                children = cmds.listRelatives(first, ad=True, type="transform", fullPath=True) or []
                return self._sort_chain(children)
        if not hier_mode:
            return self._sort_chain(sel)
        children = cmds.listRelatives(sel, ad=True, type="transform", fullPath=True) or [] if sel else []
        merged = list(dict.fromkeys(sel + children))
        return self._sort_chain(merged)

    @staticmethod
    def _sort_chain(ctrls):
        def depth(c):
            fp = cmds.ls(c, long=True)
            return fp[0].count("|") if fp else 0
        return sorted(ctrls, key=depth)

    @staticmethod
    def _channel_blocked(node, ch):
        plug = f"{node}.{ch}"
        if not cmds.objExists(plug): return True
        try:
            if cmds.getAttr(plug, lock=True): return True
            if not cmds.getAttr(plug, keyable=True): return True
        except: return True
        return False

    def _resolve_range(self, use_range, range_start, range_end):
        if use_range: return int(range_start), int(range_end)
        return (int(cmds.playbackOptions(q=True, min=True)), int(cmds.playbackOptions(q=True, max=True)))

    @staticmethod
    def _progress(done, total, phase, name):
        if cmds.progressWindow(q=True, isCancelled=True): raise UserCancelled()
        pct = int(done / max(1, total) * 100)
        short = name.rsplit("|", 1)[-1]
        cmds.progressWindow(e=True, progress=min(pct, 100), status=f"{phase}: {short}  ({pct}%)")

    @staticmethod
    def _scale_quat(q, t):
        if q.w < 0.0: q = om.MQuaternion(-q.x, -q.y, -q.z, -q.w)
        angle = 2.0 * math.acos(max(-1.0, min(1.0, q.w)))
        if angle < 1e-9: return om.MQuaternion()
        s = math.sin(angle * 0.5)
        ax, ay, az = q.x / s, q.y / s, q.z / s
        half = angle * t * 0.5
        sh   = math.sin(half)
        return om.MQuaternion(ax * sh, ay * sh, az * sh, math.cos(half))

    @staticmethod
    def _matrix_to_local_trs(local_mtx, rot_order):
        tfm = om.MTransformationMatrix(local_mtx)
        t   = tfm.translation(om.MSpace.kWorld)
        e   = tfm.rotation(asQuaternion=False)
        try: e = e.reorder(rot_order)
        except: pass
        return ([t.x, t.y, t.z], [math.degrees(e.x), math.degrees(e.y), math.degrees(e.z)])

    @staticmethod
    def _unroll_to_prev(value, prev):
        if prev is None: return value
        while value - prev > 180.0: value -= 360.0
        while value - prev < -180.0: value += 360.0
        return value

    @staticmethod
    def _source_frame(f, delay, start, end, cycle_mode):
        sf = f - delay
        if cycle_mode and sf < start: sf = end - (start - sf)
        return sf

    @staticmethod
    def _wind_offset(f, d_idx, wind_dir, wind_strength):
        wave    = math.sin(f * 0.2) + 0.35 * math.sin(f * 0.53 + 1.7)
        eff_str = wind_strength * (1.0 + 0.5 * d_idx)
        return [wind_dir[i] * wave * eff_str for i in range(3)]

    @staticmethod
    def _needs_scrub(ctrls):
        """컨트롤(또는 상위 노드)이 컨스트레인트로 구동되면 True.
        그 경우 getAttr(-time) 대신 타임 스크럽으로 월드 모션을 샘플링해야 한다."""
        CON_TYPES = ("parentConstraint", "pointConstraint", "orientConstraint",
                     "scaleConstraint", "aimConstraint", "pointOnPolyConstraint",
                     "geometryConstraint", "normalConstraint", "tangentConstraint")
        for c in ctrls:
            node = c
            chain = []
            cur = cmds.ls(c, long=True)
            cur = cur[0] if cur else c
            while cur:
                chain.append(cur)
                par = cmds.listRelatives(cur, parent=True, fullPath=True)
                cur = par[0] if par else None
            for n in chain:
                cons = cmds.listConnections(n, source=True, destination=False) or []
                for con in cons:
                    if cmds.nodeType(con) in CON_TYPES:
                        return True
        return False

    def _bake_all(self, layer_name, initial_sel, final_list,
                  start, end, delay, scale, smoothing, decay,
                  locks, hier_mode, cycle_mode,
                  wind_enable, wind_dir, wind_strength,
                  custom_enable, custom_in, custom_out, custom_gain,
                  physics_enable, overshoot):

        sorted_ctrls = self._sort_chain(final_list)
        n_ctrls      = len(sorted_ctrls)
        total_units  = n_ctrls + (end - start + 1)
        done_units   = 0

        root_depth_map = {
            s: cmds.ls(s, long=True)[0].count("|") for s in initial_sel
        }

        def depth_index(ctrl):
            fp   = cmds.ls(ctrl, long=True)[0]
            cdep = fp.count("|")
            best = None
            for rp, rd in root_depth_map.items():
                if fp == rp or fp.startswith(rp + "|"):
                    d = cdep - rd
                    best = d if best is None else min(best, d)
            return best if best is not None else 0

        min_frame = start if cycle_mode else start - delay

        # 컨스트레인트로 구동되는 컨트롤은 getAttr(-time)이 모션을 못 읽으므로
        # 타임라인을 스크럽하며 샘플링한다(일반 애님 커브 컨트롤은 기존 빠른 경로 유지).
        needs_scrub = self._needs_scrub(sorted_ctrls)

        all_data = {}
        for ctrl in sorted_ctrls:
            try: ro = cmds.getAttr(f"{ctrl}.rotateOrder")
            except: ro = 0
            rot_order = ROT_ORDERS[ro] if 0 <= ro < 6 else ROT_ORDERS[0]
            all_data[ctrl] = {"world": {}, "pinv": {}, "rot_order": rot_order}

        if needs_scrub:
            saved_time = cmds.currentTime(q=True)
            try:
                for f in range(min_frame, end + 1):
                    cmds.currentTime(f, edit=True, update=True)
                    for ctrl in sorted_ctrls:
                        wm  = om.MMatrix(cmds.getAttr(f"{ctrl}.worldMatrix[0]"))
                        tfm = om.MTransformationMatrix(wm)
                        pos = tfm.translation(om.MSpace.kWorld)
                        qt  = tfm.rotation(asQuaternion=True)
                        all_data[ctrl]["world"][f] = ([pos.x, pos.y, pos.z], qt)
                        if f >= start:
                            all_data[ctrl]["pinv"][f] = om.MMatrix(cmds.getAttr(f"{ctrl}.parentInverseMatrix[0]"))
                    self._progress(done_units, total_units, "Sampling", f"Frame {f}")
            finally:
                cmds.currentTime(saved_time, edit=True, update=True)
            done_units += n_ctrls
        else:
            for ctrl in sorted_ctrls:
                world = all_data[ctrl]["world"]
                pinv  = all_data[ctrl]["pinv"]
                for f in range(min_frame, end + 1):
                    wm  = om.MMatrix(cmds.getAttr(f"{ctrl}.worldMatrix[0]", time=f))
                    tfm = om.MTransformationMatrix(wm)
                    pos = tfm.translation(om.MSpace.kWorld)
                    qt  = tfm.rotation(asQuaternion=True)
                    world[f] = ([pos.x, pos.y, pos.z], qt)
                    if f >= start:
                        pinv[f] = om.MMatrix(cmds.getAttr(f"{ctrl}.parentInverseMatrix[0]", time=f))
                done_units += 1
                self._progress(done_units, total_units, "Sampling", ctrl)

        ctrl_states = {c: {
            "sm_prev": {ch: 0.0 for ch in CHANNELS},
            "prev_dval": {ch: None for ch in ROT_CHANNELS},
            "custom_prev_in": None,
            "phys_vel": {ch: 0.0 for ch in CHANNELS},
            "phys_pos": {ch: 0.0 for ch in CHANNELS},
        } for c in sorted_ctrls}

        for f in range(start, end + 1):
            for ctrl in sorted_ctrls:
                data = all_data[ctrl]
                world = data["world"]
                pinv = data["pinv"]
                rot_order = data["rot_order"]
                d_idx = depth_index(ctrl)
                amp = scale * (decay ** d_idx)
                
                state = ctrl_states[ctrl]
                sm_prev = state["sm_prev"]
                prev_dval = state["prev_dval"]
                phys_vel = state["phys_vel"]
                phys_pos = state["phys_pos"]
                
                sf = self._source_frame(f, delay, start, end, cycle_mode)
                p_base, q_base = world[f]
                p_src, q_src = world.get(sf, world[min(world)])
                
                p_target = [p_base[i] + (p_src[i] - p_base[i]) * amp for i in range(3)]
                q_off = q_src * q_base.inverse()
                q_scaled = self._scale_quat(q_off, amp)
                q_target = q_scaled * q_base
                
                tfm_t = om.MTransformationMatrix()
                tfm_t.setRotation(q_target.asEulerRotation())
                tfm_t.setTranslation(om.MVector(*p_target), om.MSpace.kWorld)
                world_target = tfm_t.asMatrix()
                pim = pinv[f]
                local_target = world_target * pim

                tfm_b = om.MTransformationMatrix()
                tfm_b.setRotation(q_base.asEulerRotation())
                tfm_b.setTranslation(om.MVector(*p_base), om.MSpace.kWorld)
                local_base = tfm_b.asMatrix() * pim

                t_t, r_t = self._matrix_to_local_trs(local_target, rot_order)
                t_b, r_b = self._matrix_to_local_trs(local_base,  rot_order)

                deltas = {}
                for i, ch in enumerate(ROT_CHANNELS):
                    dv = r_t[i] - r_b[i]
                    dv = self._unroll_to_prev(dv, prev_dval[ch])
                    prev_dval[ch] = dv
                    deltas[ch] = dv
                for i, ch in enumerate(TR_CHANNELS):
                    deltas[ch] = t_t[i] - t_b[i]

                if wind_enable:
                    wind = self._wind_offset(f, d_idx, wind_dir, wind_strength)
                    for i, ch in enumerate(ROT_CHANNELS): deltas[ch] += wind[i]

                if custom_enable and custom_in in CHANNELS and custom_out in CHANNELS:
                    src_dv = deltas.get(custom_in, 0.0)
                    if custom_in in ROT_CHANNELS:
                        src_dv = self._unroll_to_prev(src_dv, state["custom_prev_in"])
                        state["custom_prev_in"] = src_dv
                    deltas[custom_out] = (deltas.get(custom_out, 0.0) + src_dv * custom_gain)

                for ch, dv in deltas.items():
                    if locks.get(ch, False): continue
                    if self._channel_blocked(ctrl, ch): continue

                    if physics_enable:
                        stiffness = 0.15 + (1.0 - smoothing) * 0.2
                        damping = 0.95 - (overshoot * 0.3)
                        accel = (dv - phys_pos[ch]) * stiffness
                        phys_vel[ch] = (phys_vel[ch] + accel) * damping
                        phys_pos[ch] += phys_vel[ch]
                        final_dv = phys_pos[ch]
                    else:
                        if smoothing > 0:
                            dv = dv * (1.0 - smoothing) + sm_prev[ch] * smoothing
                        sm_prev[ch] = dv
                        final_dv = dv

                    cmds.setKeyframe(ctrl, attribute=ch, time=f, value=final_dv, animLayer=layer_name)

            done_units += 1
            self._progress(done_units, total_units, "Baking", f"Frame {f}")

        cmds.progressWindow(e=True, status="Filtering curves... (100%)", progress=100)
        layer_curves = cmds.animLayer(layer_name, q=True, animCurves=True)
        if layer_curves:
            try: cmds.filterCurve(layer_curves)
            except: pass
# ══════════════════════════════════════════════════════════════
#  VertexMapEngine  (Surface VertexMap Builder)
# ══════════════════════════════════════════════════════════════
class VertexMapEngine:
    """
    메쉬 표면 버텍스 선택을 기반으로, 스킨 인플루언스로 동작하는 컨트롤러를 생성한다.
      - 버텍스 1개      → 'Soft'  : 조인트 1개 + 중심에서 둥글게 자동 폴오프 페인트(소프트 셀렉션 방식)
      - 버텍스 2개 이상 → 'Joint' : 조인트 N개 + 사용자가 직접 스킨 웨이트 페인트

    공통:
      * Scale  : 영향 반경(=스피어 컨트롤의 가시 크기). 컨트롤 트랜스폼은 항상 깨끗하게 유지하고
                 셰이프 CV만 스케일하므로, 범위를 키워도 지글 진폭(애니메이션 값)에는 영향이 없다.
      * Weight : 중심에서의 최대 가중치(0~1).
      * Effect : 폴오프 집중도(지수). 1=기본, >1=중심에 더 집중, <1=더 넓게.
      * 생성/수정한 결과는 즉시 뷰포트에 반영(스피어 리사이즈 + 스킨 웨이트 재페인트 + 컬러 피드백).
      * 생성된 스피어 컨트롤을 Overlap 탭에서 선택 후 Apply 하면 세컨더리 모션이 베이크된다.
    """

    ROOT_GRP = "SecondMotion_GRP"
    MAIN_GRP = "VertexMap_GRP"

    def __init__(self):
        self._items = []       # [{name,type,mesh,skin,joints,holder,ctrls,offsets,
                               #   center_pos,radius,weight,effect,fmode,fcurve,vis_scale}]
        self.last_mesh = None
        self._callbacks = {}   # name -> [callback ids]
        self._deleting  = set()

    # ---- public ----------------------------------------------------------
    def items(self):
        self._items = [it for it in self._items
                       if it["ctrls"] and cmds.objExists(it["ctrls"][0])]
        return self._items

    def get(self, name):
        for it in self._items:
            if it["name"] == name:
                return it
        return None

    def create_from_selection(self, shape, name, scale, weight, effect,
                              falloff_mode, falloff_curve, orient_world):
        verts = self._selected_vertices()
        if not verts:
            raise RuntimeError("메쉬의 버텍스(Vertex)를 1개 이상 선택해 주세요.")

        mesh = verts[0].split(".")[0]
        self.last_mesh = mesh
        base = self._make_base_name(name, mesh)

        if len(verts) == 1:
            item = self._create_soft(mesh, verts[0], shape, base, scale, weight,
                                     effect, falloff_mode, falloff_curve, orient_world)
        else:
            item = self._create_joint(mesh, verts, shape, base, scale, orient_world)

        self._items.append(item)
        self._register_delete_callbacks(item)
        cmds.select(item["ctrls"], replace=True)
        return item

    def delete_item(self, name):
        self._deleting.add(name)
        self._remove_callbacks(name)
        try:
            for it in list(self._items):
                if it["name"] == name:
                    self._remove_influences(it)
                    live = [n for n in it["nodes"] if cmds.objExists(n)]
                    if live:
                        cmds.delete(live)
                    self._items.remove(it)
                    self._cleanup_empty_groups()
                    return True
            return False
        finally:
            self._deleting.discard(name)

    def item_from_selection(self):
        """씬에서 선택된 노드가 속한 VM 아이템 이름을 찾는다(스피어/큐브/조인트/그룹 등)."""
        sel = cmds.ls(selection=True, long=True) or []
        if not sel:
            return None
        sel_short = set(s.split("|")[-1] for s in sel)
        for it in self.items():
            cand = list(it.get("ctrls", [])) + list(it.get("offsets", [])) \
                   + list(it.get("joints", [])) + [it.get("item_grp"), it.get("holder")]
            for n in cand:
                if not n:
                    continue
                if n in sel or n.split("|")[-1] in sel_short:
                    return it["name"]
            # item_grp 하위 전체도 확인
            grp = it.get("item_grp")
            if grp and cmds.objExists(grp):
                desc = cmds.listRelatives(grp, allDescendents=True, fullPath=True) or []
                desc_short = set(d.split("|")[-1] for d in desc)
                if sel_short & desc_short:
                    return it["name"]
        return None

    # ---- deletion callbacks (아웃라이너에서 직접 지워도 연관 노드 정리) ----
    def _register_delete_callbacks(self, item):
        ids = []
        for ctrl in item["ctrls"]:
            try:
                msel = om.MSelectionList()
                msel.add(ctrl)
                obj = msel.getDependNode(0)
                name = item["name"]
                cb = om.MNodeMessage.addNodePreRemovalCallback(
                    obj, lambda *a, n=name: self._on_node_removed(n))
                ids.append(cb)
            except Exception:
                pass
        self._callbacks[item["name"]] = ids

    def _remove_callbacks(self, name):
        for cb in self._callbacks.pop(name, []):
            try:
                om.MMessage.removeCallback(cb)
            except Exception:
                pass

    def _on_node_removed(self, name):
        if name in self._deleting:
            return
        self._deleting.add(name)
        # 삭제 콜백 도중 씬을 수정하지 않도록 지연 실행
        cmds.evalDeferred(lambda n=name: self._cascade_delete(n))

    def _cascade_delete(self, name):
        try:
            self._remove_callbacks(name)
            it = self.get(name)
            if it:
                self._remove_influences(it)
                live = [n for n in it["nodes"] if cmds.objExists(n)]
                if live:
                    cmds.delete(live)
                if it in self._items:
                    self._items.remove(it)
            self._cleanup_empty_groups()
        except Exception:
            pass
        finally:
            self._deleting.discard(name)

    def _remove_influences(self, it):
        skin = it.get("skin")
        if not (skin and cmds.objExists(skin)):
            return
        existing = cmds.skinCluster(skin, q=True, influence=True) or []
        targets = list(it.get("joints", []))
        if it.get("holder"):
            targets.append(it["holder"])
        for j in targets:
            if j and j in existing:
                try:
                    cmds.skinCluster(skin, edit=True, removeInfluence=j)
                except Exception:
                    pass

    def _cleanup_empty_groups(self):
        """남은 항목이 없으면 비어 있는 상위 그룹(VertexMap_GRP, SecondMotion_GRP)도 삭제."""
        for grp in (self.MAIN_GRP, self.ROOT_GRP):
            if cmds.objExists(grp):
                children = cmds.listRelatives(grp, children=True, fullPath=True) or []
                if not children:
                    try:
                        cmds.delete(grp)
                    except Exception:
                        pass

    def select_item(self, name):
        it = self.get(name)
        if it:
            live = [c for c in it["ctrls"] if cmds.objExists(c)]
            if live:
                cmds.select(live, replace=True)

    # ---- mode 1 : Soft (joint + auto round paint) ------------------------
    def _create_soft(self, mesh, vtx, shape, base, scale, weight, effect,
                     falloff_mode, falloff_curve, orient_world):
        center_idx = int(vtx.split("[")[1].rstrip("]"))
        pos = cmds.pointPosition(vtx, world=True)

        cmds.select(clear=True)
        jnt = cmds.joint(name=base + "_JNT", position=(pos[0], pos[1], pos[2]))
        cmds.setAttr(jnt + ".radius", max(0.01, float(scale) * 0.25))
        cmds.select(clear=True)

        skin, holder = self._ensure_skin(mesh, base, [jnt])

        ctrl, grp = self._make_control(shape, base, scale)
        rot = (0, 0, 0)
        if not orient_world:
            rot = self._normal_euler(self._vertex_normal(vtx))
        cmds.xform(grp, worldSpace=True, translation=pos, rotation=rot)

        # 계층 정리: SecondMotion_GRP > VertexMap_GRP > <base>_GRP
        item_grp = self._ensure_item_grp(base)
        cmds.parent(grp, item_grp)
        cmds.parent(jnt, item_grp)
        if holder:
            cmds.parent(holder, item_grp)

        # 최종 부모 확정 후 제약(팝 방지)
        cmds.parentConstraint(ctrl, jnt, maintainOffset=True)
        self._follow_rig(grp, skin, mesh, center_idx, exclude=[jnt, holder])

        item = {"name": base, "type": "Soft", "mesh": mesh, "skin": skin,
                "joints": [jnt], "holder": holder, "ctrls": [ctrl],
                "offsets": [grp], "item_grp": item_grp, "nodes": [item_grp],
                "center_idx": center_idx, "center_pos": list(pos),
                "radius": float(scale), "weight": float(weight),
                "effect": float(effect), "fmode": falloff_mode,
                "fcurve": falloff_curve, "vis_scale": float(scale)}

        self._paint_soft(item)
        cmds.inViewMessage(
            amg="VertexMap: <hl>Soft</hl> created &amp; following rig. For flesh jiggle, "
                "in Overlap enable <hl>Translation</hl> (+ Physics), then Apply.",
            pos="topCenter", fade=True, fadeStayTime=2600)
        return item

    # ---- mode 2 : Joint (manual paint) -----------------------------------
    def _create_joint(self, mesh, verts, shape, base, scale, orient_world):
        joints, ctrls, offsets, centers = [], [], [], []
        item_grp = self._ensure_item_grp(base)

        for i, v in enumerate(verts):
            idx = int(v.split("[")[1].rstrip("]"))
            pos = cmds.pointPosition(v, world=True)
            cmds.select(clear=True)
            jnt = cmds.joint(name="%s_%02d_JNT" % (base, i + 1),
                             position=(pos[0], pos[1], pos[2]))
            cmds.setAttr(jnt + ".radius", max(0.01, float(scale) * 0.25))
            cmds.select(clear=True)
            joints.append(jnt)
            centers.append(idx)

            ctrl, grp = self._make_control(shape, "%s_%02d" % (base, i + 1), scale)
            rot = (0, 0, 0)
            if not orient_world:
                rot = self._normal_euler(self._vertex_normal(v))
            cmds.xform(grp, worldSpace=True, translation=pos, rotation=rot)
            ctrls.append(ctrl)
            offsets.append(grp)

        skin, holder = self._ensure_skin(mesh, base, joints)

        # 최종 부모로 정리 후 제약(팝 방지)
        for jnt, grp, idx in zip(joints, offsets, centers):
            cmds.parent(grp, item_grp)
            cmds.parent(jnt, item_grp)
        if holder:
            cmds.parent(holder, item_grp)
        for jnt, grp, ctrl, idx in zip(joints, offsets, ctrls, centers):
            cmds.parentConstraint(ctrl, jnt, maintainOffset=True)
            self._follow_rig(grp, skin, mesh, idx, exclude=joints + [holder])

        cmds.select(ctrls, replace=True)
        cmds.inViewMessage(
            amg="VertexMap: <hl>Joint</hl> controller created (%d joints). "
                "Press <hl>Paint</hl> to assign skin weights." % len(joints),
            pos="topCenter", fade=True, fadeStayTime=2400)
        return {"name": base, "type": "Joint", "mesh": mesh, "skin": skin,
                "joints": joints, "holder": holder, "ctrls": ctrls,
                "offsets": offsets, "item_grp": item_grp, "nodes": [item_grp],
                "vis_scale": float(scale)}

    # ---- live editing (Soft items) ---------------------------------------
    def set_visual_scale(self, name, scale):
        """슬라이더 드래그용: 컨트롤 스피어의 가시 크기만 즉시 변경(트랜스폼은 깨끗하게 유지)."""
        it = self.get(name)
        if not it:
            return
        factor = float(scale) / max(1e-6, it.get("vis_scale", 1.0))
        for c in it["ctrls"]:
            if cmds.objExists(c):
                shapes = cmds.listRelatives(c, shapes=True, fullPath=True) or []
                for sh in shapes:
                    try:
                        cmds.scale(factor, factor, factor, sh + ".cv[*]",
                                   relative=True, objectSpace=True)
                    except Exception:
                        pass
        it["vis_scale"] = float(scale)

    def update_soft(self, name, scale, weight, effect, falloff_mode, falloff_curve):
        """슬라이더 릴리즈용: 스피어 크기 + 둥근 폴오프 웨이트를 다시 계산해 즉시 반영."""
        it = self.get(name)
        if not it or it["type"] != "Soft":
            return
        self.set_visual_scale(name, scale)
        it["radius"] = float(scale)
        it["weight"] = float(weight)
        it["effect"] = float(effect)
        it["fmode"]  = falloff_mode
        it["fcurve"] = falloff_curve
        if cmds.objExists(it["joints"][0]):
            cmds.setAttr(it["joints"][0] + ".radius", max(0.01, float(scale) * 0.25))
        self._paint_soft(it)
        self._refresh_weight_color(it["mesh"], it["joints"][0])

    # ---- skin weight painting (Soft) -------------------------------------
    def _paint_soft(self, item):
        mesh   = item["mesh"]
        skin   = item["skin"]
        joint  = item["joints"][0]
        radius = max(1e-4, item["radius"])
        center = item["center_pos"]
        peak   = max(0.0, item["weight"])     # 상한 없음 (>1 → 중심부 plateau 확대)
        effect = max(0.05, item["effect"])

        if item["fmode"] == "Surface":
            dist = self._surface_distances(mesh, item["center_idx"], radius)
        else:
            dist = self._volume_distances(mesh, center, radius)

        # 반경 안의 모든 버텍스: 둥근 폴오프 가중치 산출. (스킨 웨이트는 1.0로 클램프)
        new_weights = {}
        for idx, d in dist.items():
            t = min(1.0, d / radius)
            w = (self._falloff(t, item["fcurve"]) ** effect) * peak
            new_weights[idx] = min(1.0, w)

        if not new_weights:
            new_weights = {item["center_idx"]: min(1.0, peak)}

        # 반경이 줄어 이전에 칠했지만 지금은 범위 밖인 버텍스는 0으로 정리(halo 방지)
        prev = item.get("painted", set())
        stale = prev - set(new_weights.keys())
        for idx in stale:
            new_weights.setdefault(idx, 0.0)

        # 비슷한 값끼리 묶어 skinPercent 호출 수를 줄임(성능)
        buckets = {}
        for idx, w in new_weights.items():
            buckets.setdefault(round(w, 3), []).append(idx)

        for w, idxs in buckets.items():
            comps = ["%s.vtx[%d]" % (mesh, i) for i in idxs]
            try:
                cmds.skinPercent(skin, comps, transformValue=[(joint, w)])
            except Exception:
                for c in comps:
                    try:
                        cmds.skinPercent(skin, c, transformValue=[(joint, w)])
                    except Exception:
                        pass

        item["painted"] = set(k for k, v in new_weights.items() if v > 1e-5)

    @staticmethod
    def _falloff(t, curve):
        t = max(0.0, min(1.0, t))
        if curve == "Linear":
            return 1.0 - t
        if curve == "Flat":
            return 1.0 if t < 0.999 else 0.0
        if curve == "Spline":
            return 1.0 - (3.0 * t * t - 2.0 * t * t * t)   # smoothstep
        # Smooth (기본): 코사인 돔
        return (math.cos(math.pi * t) + 1.0) * 0.5

    # ---- distance helpers ------------------------------------------------
    @staticmethod
    def _mesh_dagpath(mesh):
        sel = om.MSelectionList()
        sel.add(mesh)
        dag = sel.getDagPath(0)
        dag.extendToShape()
        return dag

    def _volume_distances(self, mesh, center, radius):
        """중심점으로부터 유클리드(3D) 거리. {vtxIndex: distance} (반경 이내만)."""
        dag = self._mesh_dagpath(mesh)
        fn  = om.MFnMesh(dag)
        pts = fn.getPoints(om.MSpace.kWorld)
        c   = om.MPoint(center[0], center[1], center[2])
        out = {}
        r2  = radius * radius
        for i in range(len(pts)):
            dx = pts[i].x - c.x
            dy = pts[i].y - c.y
            dz = pts[i].z - c.z
            d2 = dx * dx + dy * dy + dz * dz
            if d2 <= r2:
                out[i] = math.sqrt(d2)
        return out

    def _surface_distances(self, mesh, center_idx, radius):
        """엣지 그래프 기반 측지(geodesic) 근사 거리(다익스트라). {vtxIndex: distance}."""
        import heapq
        dag = self._mesh_dagpath(mesh)
        fn  = om.MFnMesh(dag)
        pts = fn.getPoints(om.MSpace.kWorld)

        it_v = om.MItMeshVertex(dag)
        adj  = {}
        while not it_v.isDone():
            i = it_v.index()
            adj[i] = list(it_v.getConnectedVertices())
            it_v.next()

        dist = {center_idx: 0.0}
        heap = [(0.0, center_idx)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, 1e18):
                continue
            for w in adj.get(u, []):
                edge = (pts[u] - pts[w]).length()
                nd = d + edge
                if nd <= radius and nd < dist.get(w, 1e18):
                    dist[w] = nd
                    heapq.heappush(heap, (nd, w))
        return dist

    # ---- skin / scene helpers --------------------------------------------
    def _ensure_skin(self, mesh, base, joints):
        """기존 skinCluster가 있으면 인플루언스로 추가, 없으면 holder 조인트와 함께 새로 바인드.
        returns (skinCluster, holder_joint_or_None)"""
        skin = self._find_skincluster(mesh)
        holder = None
        if skin:
            existing = cmds.skinCluster(skin, q=True, influence=True) or []
            for j in joints:
                if j not in existing:
                    cmds.skinCluster(skin, edit=True, addInfluence=j,
                                     weight=0.0, lockWeights=False)
            return skin, None

        # 스킨이 없는 메쉬: 나머지 가중치를 담을 holder 조인트 생성 후 바인드
        bbox = cmds.exactWorldBoundingBox(mesh)
        cx = (bbox[0] + bbox[3]) * 0.5
        cy = (bbox[1] + bbox[4]) * 0.5
        cz = (bbox[2] + bbox[5]) * 0.5
        cmds.select(clear=True)
        holder = cmds.joint(name=base + "_HOLDER_JNT", position=(cx, cy, cz))
        cmds.setAttr(holder + ".visibility", 0)
        cmds.select(clear=True)
        skin = cmds.skinCluster([holder] + joints + [mesh], toSelectedBones=True,
                                bindMethod=0, skinMethod=0, normalizeWeights=1)[0]
        return skin, holder

    @staticmethod
    def _refresh_weight_color(mesh, joint):
        """스킨 페인트 컨텍스트가 켜져 있으면 컬러 피드백을 새 가중치로 갱신."""
        try:
            ctx = cmds.currentCtx()
            if ctx and "artAttrSkin" in ctx:
                mel.eval('artSkinSelectInfluence("%s", "%s")' % (ctx, joint))
        except Exception:
            pass

    @staticmethod
    def _selected_vertices():
        sel = cmds.ls(selection=True, flatten=True) or []
        return [s for s in sel if ".vtx[" in s]

    def _make_base_name(self, name, mesh):
        short = (name or mesh).split("|")[-1]
        short = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in short)
        cand = short + "_VM"
        n = 1
        while cmds.objExists(cand + "_CTRL") or cmds.objExists(cand + "_01_JNT") \
                or cmds.objExists(cand + "_JNT"):
            n += 1
            cand = "%s_VM%d" % (short, n)
        return cand

    def _ensure_main_grp(self):
        if not cmds.objExists(self.ROOT_GRP):
            cmds.group(empty=True, name=self.ROOT_GRP)
        if not cmds.objExists(self.MAIN_GRP):
            cmds.group(empty=True, name=self.MAIN_GRP, parent=self.ROOT_GRP)
        else:
            par = cmds.listRelatives(self.MAIN_GRP, parent=True) or []
            if not par or par[0].split("|")[-1] != self.ROOT_GRP:
                cmds.parent(self.MAIN_GRP, self.ROOT_GRP)
        return self.MAIN_GRP

    def _ensure_item_grp(self, base):
        """SecondMotion_GRP > VertexMap_GRP > <base>_GRP 를 만들고 <base>_GRP 반환."""
        main = self._ensure_main_grp()
        name = base + "_GRP"
        n = 1
        while cmds.objExists(name):
            n += 1
            name = "%s_GRP%d" % (base, n)
        return cmds.group(empty=True, name=name, parent=main)

    def _follow_rig(self, offset_grp, skin, mesh, vtx_index, exclude):
        """컨트롤(오프셋)이 해당 버텍스의 주된 리그 조인트를 따라가게 한다.
        → 몸이 움직이면 컨트롤도 따라가고, Overlap이 lag를 베이크하면 출렁임(jiggle)이 생김.
        디포메이션된 메쉬가 아닌 리그 조인트를 따르므로 순환 의존성이 없다."""
        dom = self._dominant_influence(skin, mesh, vtx_index, exclude)
        if dom and cmds.objExists(dom) and dom != offset_grp:
            try:
                cmds.parentConstraint(dom, offset_grp, maintainOffset=True)
            except Exception:
                pass
        return dom

    @staticmethod
    def _dominant_influence(skin, mesh, vtx_index, exclude):
        if not skin:
            return None
        vtx = "%s.vtx[%d]" % (mesh, vtx_index)
        try:
            infs = cmds.skinPercent(skin, vtx, q=True, transform=None) or []
            vals = cmds.skinPercent(skin, vtx, q=True, value=True) or []
        except Exception:
            return None
        excl = set(x for x in (exclude or []) if x)
        best, bw = None, -1.0
        for inf, w in zip(infs, vals):
            if inf in excl:
                continue
            if w > bw:
                bw, best = w, inf
        return best

    def _make_control(self, shape, base, scale):
        """컨트롤 커브 + 오프셋 그룹 생성. (ctrl, offset_grp) 반환.
        스케일은 CV에 직접 적용(트랜스폼은 identity 유지)."""
        if shape == "Cube":
            pts = [(-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1), (-1, 1, 1),
                   (-1, -1, 1), (1, -1, 1), (1, 1, 1), (1, -1, 1), (1, -1, -1),
                   (1, 1, -1), (1, -1, -1), (-1, -1, -1), (-1, 1, -1),
                   (-1, -1, -1), (-1, -1, 1)]
            ctrl = cmds.curve(degree=1, point=pts, name=base + "_CTRL")
        else:  # Sphere : 3축 와이어 원
            circles = [cmds.circle(normal=ax, radius=1, constructionHistory=False)[0]
                       for ax in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]]
            ctrl = cmds.group(empty=True, name=base + "_CTRL")
            for c in circles:
                sh = cmds.listRelatives(c, shapes=True, fullPath=True)[0]
                cmds.parent(sh, ctrl, relative=True, shape=True)
                cmds.delete(c)

        # CV 스케일 (트랜스폼은 건드리지 않음)
        for sh in (cmds.listRelatives(ctrl, shapes=True, fullPath=True) or []):
            try:
                cmds.scale(scale, scale, scale, sh + ".cv[*]",
                           relative=True, objectSpace=True)
            except Exception:
                pass

        grp = cmds.group(ctrl, name=base + "_OFFSET")
        return ctrl, grp

    @staticmethod
    def _vertex_normal(vtx):
        mesh = vtx.split(".")[0]
        idx  = int(vtx.split("[")[1].rstrip("]"))
        sel  = om.MSelectionList()
        sel.add(mesh)
        dag = sel.getDagPath(0)
        dag.extendToShape()
        fn = om.MFnMesh(dag)
        n  = fn.getVertexNormal(idx, True, om.MSpace.kWorld)
        return [n.x, n.y, n.z]

    @staticmethod
    def _normal_euler(normal):
        up = om.MVector(0, 1, 0)
        n  = om.MVector(normal[0], normal[1], normal[2]).normal()
        if up.isEquivalent(n, 1e-4):
            return (0, 0, 0)
        q = om.MQuaternion(up, n)
        e = q.asEulerRotation()
        return (math.degrees(e.x), math.degrees(e.y), math.degrees(e.z))

    @staticmethod
    def _find_skincluster(mesh):
        try:
            sc = mel.eval('findRelatedSkinCluster("%s")' % mesh)
            if sc:
                return sc
        except Exception:
            pass
        shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True,
                                    noIntermediate=True) or []
        for s in shapes:
            hist = cmds.listHistory(s, pruneDagObjects=True) or []
            scs  = cmds.ls(hist, type="skinCluster")
            if scs:
                return scs[0]
        return None


class SecondMotionUI:
    WINDOW_NAME = "secondMotionWinV252"

    AXIS_LABELS = ["Rotate X", "Rotate Y", "Rotate Z",
                   "Translate X", "Translate Y", "Translate Z"]
    AXIS_KEYS   = CHANNELS

    def __init__(self):
        self._ui        = {}
        self._presets   = PresetManager()
        self._overlap   = OverlapEngine()
        self._builder   = VertexMapEngine()
        self._active_vm = None

    def show(self):
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME)

        win      = cmds.window(self.WINDOW_NAME, title="SecondMotion v2.6.6", widthHeight=(400, 875))
        scroll   = cmds.scrollLayout(childResizable=True, verticalScrollBarThickness=16)
        main_col = cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

        cmds.frameLayout(labelVisible=False, marginHeight=10, backgroundColor=[0.18, 0.22, 0.38])
        cmds.text(label="SECOND MOTION v2.6.6", font="boldLabelFont", align="center")
        cmds.setParent("..")

        tabs = cmds.tabLayout(innerMarginWidth=5, innerMarginHeight=5)
        tab1 = self._build_tab1(tabs)
        cmds.setParent(tabs)
        tab2 = self._build_tab2(tabs)
        cmds.setParent(tabs)
        tab3 = self._build_tab3(tabs)
        cmds.setParent("..")
        cmds.tabLayout(tabs, edit=True, tabLabel=[(tab1, "  Overlap  "),
                                                  (tab2, "  VertexMap  "),
                                                  (tab3, "  About  ")])

        cmds.setParent(main_col)
        cmds.showWindow(win)

        self._refresh_layer_list()
        self._refresh_vm_list()

    def _build_tab1(self, tabs):
        tab1 = cmds.columnLayout(adjustableColumn=True, rowSpacing=5)

        self._build_preset_section()
        
        cmds.frameLayout(label="Main Operation Mode", marginHeight=8, marginWidth=15, backgroundColor=[0.24, 0.24, 0.24])
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        cmds.rowLayout(numberOfColumns=4, columnWidth4=[80, 95, 75, 70])
        self._ui["mode_rotation"]    = cmds.checkBox(label="Rotation", value=True)
        self._ui["mode_translation"] = cmds.checkBox(label="Translation", value=False)
        self._ui["mode_physics"]     = cmds.checkBox(label="Physics", value=False)
        self._ui["mode_custom"]      = cmds.checkBox(label="Custom", value=False)
        cmds.setParent("..")
        cmds.separator(height=6, style="in")
        cmds.rowLayout(numberOfColumns=4, columnWidth4=[60, 60, 60, 60])
        cmds.text(label="Axis: ", font="boldLabelFont")
        self._ui["axis_x"] = cmds.checkBox(label="X", value=True)
        self._ui["axis_y"] = cmds.checkBox(label="Y", value=True)
        self._ui["axis_z"] = cmds.checkBox(label="Z", value=True)
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.frameLayout(labelVisible=False, marginHeight=5, marginWidth=15)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        self._float_row("Smoothness (Softness)", "soft_field",   3.0)
        self._float_row("Smoothing",             "smooth_field", 0.1, mn=0.0, mx=0.95)
        self._float_row("Scale",                 "scale_field",  0.8)
        self._float_row("Overshoot",             "overshoot_field", 0.5, step=0.1, mn=0.0, mx=1.0)
        
        cmds.separator(height=5, style="in")
        self._ui["hier_mode"]    = cmds.checkBox(label="Hierarchy Mode", value=True)
        self._ui["ignore_first"] = cmds.checkBox(label="Ignore First Control", value=False)
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.separator(height=5, style="none")
        
        # [원클릭 버튼 그룹] APPLY & DELETE CURRENT
        cmds.button(label="APPLY SECOND MOTION", height=46,
                    backgroundColor=[0.28, 0.38, 0.58],
                    command=lambda _: self._on_apply_overlap())
        cmds.separator(height=2, style="none")
        cmds.button(label="DELETE CURRENT VertexMap LAYER", height=32,
                    backgroundColor=[0.45, 0.22, 0.22],
                    command=lambda _: self._on_delete_current_layer())
        
        cmds.separator(height=5, style="none")

        cmds.frameLayout(label=" ▶ Advanced Settings", collapsable=True, collapse=False,
                         marginHeight=10, marginWidth=10, backgroundColor=[0.2, 0.2, 0.2])
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)

        # [Animation]
        cmds.frameLayout(label=" Animation", collapsable=True, collapse=False, marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self._ui["cycle_mode"]   = cmds.checkBox(label="Cycle Mode", value=False)
        self._ui["use_range_check"] = cmds.checkBox(label="Custom Range", value=False)
        cmds.rowLayout(numberOfColumns=4, columnWidth4=[40, 75, 40, 75])
        cmds.text(label="Start")
        self._ui["range_start"] = cmds.intField(value=int(cmds.playbackOptions(q=True, min=True)))
        cmds.text(label="End")
        self._ui["range_end"] = cmds.intField(value=int(cmds.playbackOptions(q=True, max=True)))
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

        # [Chain]
        cmds.frameLayout(label=" Chain", collapsable=True, collapse=False, marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self._float_row("Decay (Chain Falloff)", "decay_field", 1.0, step=0.05, mn=0.1, mx=2.0)
        cmds.setParent("..")
        cmds.setParent("..")

        # [Wind]
        cmds.frameLayout(label=" Wind", collapsable=True, collapse=True, marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        self._ui["wind_enable"] = cmds.checkBox(label="Enable Wind", value=False)
        self._float_row("Wind Strength", "wind_strength", 1.0)
        cmds.text(label="Wind Direction  X / Y / Z", font="smallPlainLabelFont")
        cmds.rowLayout(numberOfColumns=3, columnWidth3=[95, 95, 95])
        self._ui["wind_dir_x"] = cmds.floatField(value=1.0, precision=2)
        self._ui["wind_dir_y"] = cmds.floatField(value=0.0, precision=2)
        self._ui["wind_dir_z"] = cmds.floatField(value=0.0, precision=2)
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

        # [Custom]
        cmds.frameLayout(label=" Custom Mode Option", collapsable=True, collapse=True, marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        cmds.text(label="* Enable 'Custom' mode in the top menu to apply.", font="smallObliqueLabelFont")
        cmds.rowLayout(numberOfColumns=4, columnWidth4=[50, 110, 30, 110])
        cmds.text(label="Input")
        self._ui["custom_in"] = cmds.optionMenu()
        for lab in self.AXIS_LABELS: cmds.menuItem(label=lab)
        cmds.text(label="→")
        self._ui["custom_out"] = cmds.optionMenu()
        for lab in self.AXIS_LABELS: cmds.menuItem(label=lab)
        cmds.setParent("..")
        cmds.optionMenu(self._ui["custom_in"],  e=True, select=1)
        cmds.optionMenu(self._ui["custom_out"], e=True, select=5)
        self._float_row("Mapping Gain", "custom_gain", 0.1, step=0.05)
        cmds.setParent("..")
        cmds.setParent("..")

        # [Layer Manager]
        cmds.frameLayout(label=" Layer Manager", collapsable=True, collapse=True, marginWidth=5, marginHeight=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        self._ui["layer_list"] = cmds.textScrollList(height=70, allowMultiSelection=False, selectCommand=lambda: self._on_layer_selected())
        self._ui["weight_slider"] = cmds.floatSliderGrp(
            label="Weight %", field=True, minValue=0.0, maxValue=150.0,
            fieldMinValue=0.0, fieldMaxValue=150.0, value=100.0, precision=0,
            columnWidth3=[70, 50, 180],
            changeCommand=lambda v: self._on_weight_changed(v),
            dragCommand=lambda v: self._on_weight_changed(v))
        cmds.rowLayout(numberOfColumns=3, columnWidth3=[90, 140, 110], adjustableColumn=2)
        cmds.button(label="Refresh", command=lambda _: self._refresh_layer_list())
        cmds.button(label="Delete Selected Layer", backgroundColor=[0.42, 0.25, 0.25], command=lambda _: self._on_delete_selected_layer())
        cmds.button(label="Delete ALL", backgroundColor=[0.45, 0.18, 0.18], command=lambda _: self._on_delete_all_layers())
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.setParent("..") 
        cmds.setParent(tab1)

        return tab1

    # ══════════════════════════════════════════════════════════
    #  TAB 2 : VertexMap
    # ══════════════════════════════════════════════════════════
    def _build_tab2(self, tabs):
        tab2 = cmds.columnLayout(adjustableColumn=True, rowSpacing=7,
                                 columnAttach=("both", 12))
        cmds.separator(height=8, style="none")

        # ── Shape + Name ───────────────────────────────────────
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2,
                       columnWidth2=[200, 150], columnAttach=[(1, "left", 0), (2, "left", 6)])
        self._ui["vm_shape"] = cmds.radioButtonGrp(
            numberOfRadioButtons=2, label="Shape ",
            labelArray2=["Cube", "Sphere"], select=2,
            columnWidth3=[48, 70, 70])
        cmds.rowLayout(numberOfColumns=2, columnWidth2=[48, 100], adjustableColumn=2)
        cmds.text(label="Name :")
        self._ui["vm_name"] = cmds.textField(placeholderText="auto")
        cmds.setParent("..")
        cmds.setParent("..")

        # ── Scale / Weight ─────────────────────────────────────
        self._ui["vm_scale"] = cmds.floatSliderGrp(
            label="Scale ", field=True, minValue=0.01, maxValue=10.0,
            value=1.0, precision=2, columnWidth3=[55, 55, 175],
            annotation="Influence range + control sphere size (live)",
            dragCommand=lambda v: self._on_vm_scale_drag(v),
            changeCommand=lambda v: self._on_vm_param_changed())
        self._ui["vm_weight"] = cmds.floatSliderGrp(
            label="Weight ", field=True, minValue=0.0, maxValue=2.0,
            fieldMinValue=0.0, fieldMaxValue=1000000.0,
            value=1.0, precision=2, columnWidth3=[55, 55, 175],
            annotation="Peak weight at center (>1 = wider full-weight plateau). No upper limit via field.",
            changeCommand=lambda v: self._on_vm_param_changed())

        cmds.separator(height=3, style="none")

        # ── Paint / Smooth / Options ───────────────────────────
        cmds.rowLayout(numberOfColumns=3, columnWidth3=[150, 150, 40],
                       adjustableColumn=1, columnAlign=(1, "center"))
        cmds.button(label="Paint", height=30, backgroundColor=[0.30, 0.34, 0.40],
                    command=lambda _: self._on_vm_paint())
        cmds.button(label="Smooth", height=30, backgroundColor=[0.30, 0.34, 0.40],
                    command=lambda _: self._on_vm_smooth())
        cmds.button(label="\u2699", height=30, width=34,
                    annotation="Paint tool options",
                    command=lambda _: self._on_vm_options())
        cmds.setParent("..")

        cmds.separator(height=3, style="none")

        # ── Effect / Falloff ───────────────────────────────────
        self._ui["vm_effect"] = cmds.floatSliderGrp(
            label="Effect ", field=True, minValue=0.05, maxValue=8.0,
            value=1.0, precision=2, columnWidth3=[55, 55, 175],
            annotation="Falloff concentration (1=normal, >1=tighter to center)",
            changeCommand=lambda v: self._on_vm_param_changed())

        cmds.rowLayout(numberOfColumns=2, columnWidth2=[100, 205], adjustableColumn=2)
        cmds.text(label="FalloffMode")
        self._ui["vm_fmode"] = cmds.optionMenu(changeCommand=lambda _: self._on_vm_param_changed())
        cmds.menuItem(label="Volume")
        cmds.menuItem(label="Surface")
        cmds.setParent("..")

        cmds.rowLayout(numberOfColumns=2, columnWidth2=[100, 205], adjustableColumn=2)
        cmds.text(label="FalloffCurve")
        self._ui["vm_fcurve"] = cmds.optionMenu(changeCommand=lambda _: self._on_vm_param_changed())
        for c in ["Smooth", "Spline", "Linear", "Flat"]:
            cmds.menuItem(label=c)
        cmds.setParent("..")

        cmds.separator(height=6, style="none")

        # ── Create + Orient ────────────────────────────────────
        cmds.rowLayout(numberOfColumns=2, columnWidth2=[150, 180], adjustableColumn=1)
        cmds.button(label="Create", height=36, backgroundColor=[0.28, 0.38, 0.58],
                    command=lambda _: self._on_vm_create())
        self._ui["vm_orient"] = cmds.checkBox(label="Orient to World Space", value=True)
        cmds.setParent("..")

        cmds.separator(height=4, style="none")

        # ── Created list ───────────────────────────────────────
        self._ui["vm_list"] = cmds.textScrollList(
            height=120, allowMultiSelection=False,
            selectCommand=lambda: self._on_vm_select_item())
        cmds.popupMenu()
        cmds.menuItem(label="Select", command=lambda _: self._on_vm_select_item())
        cmds.menuItem(label="Delete", command=lambda _: self._on_vm_delete_item())

        cmds.rowLayout(numberOfColumns=2, columnWidth2=[160, 160], adjustableColumn=1)
        cmds.button(label="Refresh", command=lambda _: self._refresh_vm_list())
        cmds.button(label="Delete Selected", backgroundColor=[0.42, 0.25, 0.25],
                    command=lambda _: self._on_vm_delete_item())
        cmds.setParent("..")

        cmds.setParent("..")
        cmds.setParent(tab2)
        return tab2

    # ══════════════════════════════════════════════════════════
    #  TAB 3 : About
    # ══════════════════════════════════════════════════════════
    def _build_tab3(self, tabs):
        tab3 = cmds.columnLayout(adjustableColumn=True, rowSpacing=8,
                                 columnAttach=("both", 18))
        cmds.separator(height=18, style="none")
        cmds.text(label="SecondMotion", font="boldLabelFont", align="center")
        cmds.text(label="v2.6.6", align="center")
        cmds.separator(height=12, style="in")
        cmds.text(align="left", label=(
            "Overlap   : 컨트롤러에 스프링-댐퍼 기반\n"
            "             세컨더리 모션을 베이크합니다.\n\n"
            "VertexMap: 메쉬 표면에 지글(Jiggle)용\n"
            "             컨트롤(스킨 인플루언스)을 추가합니다.\n"
            "   • 버텍스 1개   → Soft : 둥근 자동 폴오프\n"
            "   • 버텍스 2개+  → Joint : 직접 페인트\n\n"
            "   Scale=범위/크기, Weight=강도 (실시간)\n"
            "   생성 후 Overlap 탭에서 Apply → 지글"))
        cmds.separator(height=12, style="none")
        cmds.setParent("..")
        cmds.setParent(tab3)
        return tab3

    # ---- VertexMap events ------------------------------------------------
    def _refresh_vm_list(self, select=None):
        cmds.textScrollList(self._ui["vm_list"], e=True, removeAll=True)
        for it in self._builder.items():
            cmds.textScrollList(self._ui["vm_list"], e=True,
                                append="[%s] %s" % (it["type"], it["name"]))
        if select:
            self._select_vm_row(select)

    def _select_vm_row(self, name):
        for i, it in enumerate(self._builder.items()):
            if it["name"] == name:
                cmds.textScrollList(self._ui["vm_list"], e=True, selectIndexedItem=i + 1)
                return

    def _selected_vm_name(self):
        idx = cmds.textScrollList(self._ui["vm_list"], q=True, selectIndexedItem=True)
        if not idx:
            return None
        items = self._builder.items()
        i = idx[0] - 1
        return items[i]["name"] if 0 <= i < len(items) else None

    def _vm_active(self):
        """현재 슬라이더 편집 대상(=리스트에서 선택된 항목)."""
        return getattr(self, "_active_vm", None)

    def _on_vm_create(self):
        shape  = "Cube" if cmds.radioButtonGrp(self._ui["vm_shape"], q=True, select=True) == 1 else "Sphere"
        name   = cmds.textField(self._ui["vm_name"], q=True, text=True).strip()
        scale  = cmds.floatSliderGrp(self._ui["vm_scale"],  q=True, value=True)
        weight = cmds.floatSliderGrp(self._ui["vm_weight"], q=True, value=True)
        effect = cmds.floatSliderGrp(self._ui["vm_effect"], q=True, value=True)
        fmode  = cmds.optionMenu(self._ui["vm_fmode"],  q=True, value=True)
        fcurve = cmds.optionMenu(self._ui["vm_fcurve"], q=True, value=True)
        orient = cmds.checkBox(self._ui["vm_orient"], q=True, value=True)

        cmds.undoInfo(openChunk=True)
        try:
            item = self._builder.create_from_selection(
                shape, name, scale, weight, effect, fmode, fcurve, orient)
        except Exception as e:
            cmds.warning("VertexMap Create 실패: %s" % e)
            return
        finally:
            cmds.undoInfo(closeChunk=True)

        self._active_vm = item["name"]
        self._refresh_vm_list(select=item["name"])
        if item["type"] == "Soft":
            cmds.inViewMessage(
                amg="VertexMap: weights painted. Press <hl>Paint</hl> to view/edit "
                    "the round falloff in the viewport.",
                pos="topCenter", fade=True, fadeStayTime=2200)

    def _on_vm_select_item(self):
        name = self._selected_vm_name()
        if not name:
            return
        self._active_vm = name
        self._builder.select_item(name)
        # 선택 항목의 파라미터를 슬라이더에 반영
        it = self._builder.get(name)
        if it and it["type"] == "Soft":
            cmds.floatSliderGrp(self._ui["vm_scale"],  e=True, value=it["radius"])
            cmds.floatSliderGrp(self._ui["vm_weight"], e=True, value=it["weight"])
            cmds.floatSliderGrp(self._ui["vm_effect"], e=True, value=it["effect"])
            cmds.optionMenu(self._ui["vm_fmode"],  e=True, value=it["fmode"])
            cmds.optionMenu(self._ui["vm_fcurve"], e=True, value=it["fcurve"])

    # ---- live slider editing ----
    def _on_vm_scale_drag(self, value):
        """드래그 중: 스피어 가시 크기만 즉시 변경(가벼움)."""
        name = self._vm_active()
        if name and self._builder.get(name):
            self._builder.set_visual_scale(name, value)

    def _on_vm_param_changed(self):
        """슬라이더/메뉴 릴리즈: Soft 항목이면 둥근 폴오프 가중치를 다시 칠한다."""
        name = self._vm_active()
        it = self._builder.get(name) if name else None
        if not it:
            return
        if it["type"] != "Soft":
            # Joint 항목은 스피어 크기만 갱신
            self._builder.set_visual_scale(name, cmds.floatSliderGrp(self._ui["vm_scale"], q=True, value=True))
            return
        self._builder.update_soft(
            name,
            cmds.floatSliderGrp(self._ui["vm_scale"],  q=True, value=True),
            cmds.floatSliderGrp(self._ui["vm_weight"], q=True, value=True),
            cmds.floatSliderGrp(self._ui["vm_effect"], q=True, value=True),
            cmds.optionMenu(self._ui["vm_fmode"],  q=True, value=True),
            cmds.optionMenu(self._ui["vm_fcurve"], q=True, value=True))

    def _on_vm_delete_item(self):
        name = self._selected_vm_name()
        if not name:
            name = self._builder.item_from_selection()
        if not name:
            cmds.warning("리스트에서 항목을 선택하거나, 씬에서 해당 스피어/큐브를 선택해 주세요.")
            return
        cmds.undoInfo(openChunk=True)
        try:
            self._builder.delete_item(name)
        finally:
            cmds.undoInfo(closeChunk=True)
        if self._vm_active() == name:
            self._active_vm = None
        self._refresh_vm_list()

    # ---- paint helpers ----
    def _vm_paint_target(self):
        """현재 활성 항목의 (mesh, 페인트할 조인트). 없으면 last_mesh로 폴백."""
        name = self._vm_active()
        it = self._builder.get(name) if name else None
        if it:
            return it["mesh"], it["joints"][0]
        if self._builder.last_mesh and cmds.objExists(self._builder.last_mesh):
            return self._builder.last_mesh, None
        return None, None

    def _enter_paint(self, mesh, joint=None):
        if not mesh or not cmds.objExists(mesh):
            return
        try:
            cmds.select(mesh, replace=True)
            mel.eval("ArtPaintSkinWeightsTool;")
        except Exception as e:
            cmds.warning("Paint 툴 실행 실패: %s" % e)
            return
        # 인플루언스 포커스(실패해도 툴 진입은 유지)
        if joint and cmds.objExists(joint):
            try:
                ctx = cmds.currentCtx()
                if ctx and "artAttrSkin" in ctx:
                    mel.eval('artSkinSelectInfluence("%s", "%s")' % (ctx, joint))
            except Exception:
                pass

    def _on_vm_paint(self):
        mesh, joint = self._vm_paint_target()
        if not mesh:
            cmds.warning("먼저 컨트롤러를 생성하거나 리스트에서 선택해 주세요.")
            return
        self._enter_paint(mesh, joint)

    def _on_vm_smooth(self):
        mesh, joint = self._vm_paint_target()
        if not mesh:
            cmds.warning("먼저 컨트롤러를 생성하거나 리스트에서 선택해 주세요.")
            return
        self._enter_paint(mesh, joint)
        try:
            ctx = cmds.currentCtx()
            cmds.artAttrSkinPaintCtx(ctx, e=True, selectedattroper="smooth")
            cmds.inViewMessage(amg="VertexMap: Skin paint set to <hl>Smooth</hl>. "
                                   "Drag on the mesh to smooth weights.",
                               pos="topCenter", fade=True, fadeStayTime=2000)
        except Exception as e:
            cmds.warning("Smooth 모드 전환 실패: %s" % e)

    def _on_vm_options(self):
        try:
            mel.eval("ArtPaintSkinWeightsToolOptions;")
        except Exception as e:
            cmds.warning("Paint 옵션 창 실행 실패: %s" % e)


    def _build_preset_section(self):
        self._ui["preset_frame"] = cmds.frameLayout(label="Preset", collapsable=True, collapse=False, marginHeight=8, marginWidth=15)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        self._ui["preset_menu"] = cmds.optionMenu(label="Select ", changeCommand=lambda _: self._on_preset_selected())
        self._refresh_preset_menu()
        cmds.rowLayout(numberOfColumns=2, columnWidth2=[160, 160], adjustableColumn=2)
        cmds.button(label="Save Current", command=lambda _: self._on_save_preset())
        cmds.button(label="Delete Selected", command=lambda _: self._on_delete_preset())
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

    def _float_row(self, label, key, val, step=0.1, mn=None, mx=None):
        cmds.rowLayout(numberOfColumns=2, columnWidth2=[170, 100], adjustableColumn=2)
        cmds.text(label=label)
        kw = dict(value=val, precision=3, step=step)
        if mn is not None: kw["minValue"] = mn
        if mx is not None: kw["maxValue"] = mx
        self._ui[key] = cmds.floatField(**kw)
        cmds.setParent("..")

    def _ff(self, key):  return cmds.floatField(self._ui[key], q=True, value=True)
    def _cb(self, key):  return cmds.checkBox(self._ui[key],   q=True, value=True)
    def _int(self, key): return cmds.intField(self._ui[key],   q=True, value=True)

    def _axis_key(self, ui_key):
        idx = cmds.optionMenu(self._ui[ui_key], q=True, select=True)
        return self.AXIS_KEYS[idx - 1]

    # ---- Layer events ----
    def _refresh_layer_list(self, select=None):
        cmds.textScrollList(self._ui["layer_list"], e=True, removeAll=True)
        layers = self._overlap.list_sm_layers()
        for l in layers:
            cmds.textScrollList(self._ui["layer_list"], e=True, append=l)
        if select and select in layers:
            cmds.textScrollList(self._ui["layer_list"], e=True, selectItem=select)
            self._on_layer_selected()

    def _selected_layer(self):
        sel = cmds.textScrollList(self._ui["layer_list"], q=True, selectItem=True)
        return sel[0] if sel else None

    def _on_layer_selected(self):
        lay = self._selected_layer()
        if lay:
            w = self._overlap.get_layer_weight(lay)
            cmds.floatSliderGrp(self._ui["weight_slider"], e=True, value=w)

    def _on_weight_changed(self, value):
        lay = self._selected_layer()
        if lay: self._overlap.set_layer_weight(lay, value)

    def _on_delete_selected_layer(self):
        lay = self._selected_layer()
        if not lay:
            cmds.warning("Select a layer in the list first.")
            return
        if self._overlap.delete_sm_layer(lay):
            self._refresh_layer_list()

    def _on_delete_all_layers(self):
        r = cmds.confirmDialog(
            title="Delete ALL", message="모든 SM_ 레이어를 삭제할까요?",
            button=["Delete", "Cancel"], defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel")
        if r == "Delete":
            n = self._overlap.delete_all_sm_layers()
            cmds.warning(f"{n} SecondMotion layer(s) deleted.")
            self._refresh_layer_list()

    # ---- 신규 전용 기능: 현재 선택 컨트롤러 기반 계산된 레이어 삭제 ----
    def _on_delete_current_layer(self):
        initial_sel = cmds.ls(selection=True, long=True)
        if not initial_sel:
            cmds.warning("삭제할 애니메이션 레이어와 연관된 컨트롤러를 먼저 선택해 주세요.")
            return
            
        # 선택된 첫 번째 컨트롤러의 계산 레이어 이름 파싱
        target_layer = self._overlap.layer_name_for(initial_sel[0])
        
        if cmds.objExists(target_layer):
            if self._overlap.delete_sm_layer(target_layer):
                # [수정] 경고(Warning) 대신 메인 뷰포트에 깔끔한 인뷰 메시지로 알림 출력
                cmds.inViewMessage(amg=f"SecondMotion: Layer <color=#FF7A7A>[{target_layer}]</color> has been deleted.",
                                   pos="topCenter", fade=True, fadeStayTime=1500)
                # 스크립트 에디터에도 일반 로그로 출력
                print(f"// SecondMotion: [{target_layer}] 레이어가 성공적으로 삭제되었습니다. //")
                self._refresh_layer_list()
        else:
            cmds.warning(f"현재 선택 항목과 매칭되는 레이어 [{target_layer}] 가 씬에 존재하지 않습니다.")

    # ---- Apply ----
    def _on_apply_overlap(self):
        rot_m = self._cb("mode_rotation")
        tr_m  = self._cb("mode_translation")
        ax_x  = self._cb("axis_x")
        ax_y  = self._cb("axis_y")
        ax_z  = self._cb("axis_z")
        
        lock_rx = not (rot_m and ax_x)
        lock_ry = not (rot_m and ax_y)
        lock_rz = not (rot_m and ax_z)
        
        lock_tx = not (tr_m and ax_x)
        lock_ty = not (tr_m and ax_y)
        lock_tz = not (tr_m and ax_z)

        new_layer = self._overlap.run(
            softness            = self._ff("soft_field"),
            scale               = self._ff("scale_field"),
            smoothing           = self._ff("smooth_field"),
            decay               = self._ff("decay_field"),
            lock_rx             = lock_rx,
            lock_ry             = lock_ry,
            lock_rz             = lock_rz,
            lock_tx             = lock_tx,
            lock_ty             = lock_ty,
            lock_tz             = lock_tz,
            use_range           = self._cb("use_range_check"),
            range_start         = self._int("range_start"),
            range_end           = self._int("range_end"),
            hier_mode           = self._cb("hier_mode"),
            cycle_mode          = self._cb("cycle_mode"),
            ignore_first        = self._cb("ignore_first"),
            layer_weight        = cmds.floatSliderGrp(self._ui["weight_slider"], q=True, value=True),
            wind_enable         = self._cb("wind_enable"),
            wind_dir            = [self._ff("wind_dir_x"), self._ff("wind_dir_y"), self._ff("wind_dir_z")],
            wind_strength       = self._ff("wind_strength"),
            custom_enable       = self._cb("mode_custom"),
            custom_in           = self._axis_key("custom_in"),
            custom_out          = self._axis_key("custom_out"),
            custom_gain         = self._ff("custom_gain"),
            physics_enable      = self._cb("mode_physics"),
            overshoot           = self._ff("overshoot_field"),
        )
        self._refresh_layer_list(select=new_layer)

    def _refresh_preset_menu(self):
        presets = self._presets.load()
        items   = cmds.optionMenu(self._ui["preset_menu"], q=True, itemListLong=True)
        if items: cmds.deleteUI(items)
        for name in sorted(presets):
            cmds.menuItem(label=name, parent=self._ui["preset_menu"])

    def _on_preset_selected(self):
        sel = cmds.optionMenu(self._ui["preset_menu"], q=True, value=True)
        d   = self._presets.get(sel)
        if d:
            cmds.floatField(self._ui["soft_field"],   e=True, value=d["soft"])
            cmds.floatField(self._ui["scale_field"],  e=True, value=d["scale"])
            cmds.floatField(self._ui["smooth_field"], e=True, value=d["smooth"])
            cmds.floatField(self._ui["decay_field"],  e=True, value=d.get("decay", 1.0))

    def _on_save_preset(self):
        r = cmds.promptDialog(
            title="Save Preset", message="Preset name:",
            button=["Save", "Cancel"], defaultButton="Save", cancelButton="Cancel", dismissString="Cancel")
        if r == "Save":
            name = cmds.promptDialog(q=True, text=True)
            if name:
                self._presets.save(name, {
                    "soft":   self._ff("soft_field"),
                    "scale":  self._ff("scale_field"),
                    "smooth": self._ff("smooth_field"),
                    "decay":  self._ff("decay_field"),
                })
                self._refresh_preset_menu()
                cmds.optionMenu(self._ui["preset_menu"], e=True, value=name)

    def _on_delete_preset(self):
        sel = cmds.optionMenu(self._ui["preset_menu"], q=True, value=True)
        if self._presets.delete(sel):
            self._refresh_preset_menu()

# ══════════════════════════════════════════════════════════════
#  ENTRY
# ══════════════════════════════════════════════════════════════
SecondMotionUI().show()