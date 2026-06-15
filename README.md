# SecondMotion v2.6.6 — 사용 설명서

> Maya 2024 / Python 3 기반 세컨더리 모션(Overlap) 툴
> 컨트롤러에 스프링-댐퍼 기반 출렁임을 **애님 레이어로 베이크**하고, 리깅이 부족한 메쉬 표면에는 **VertexMap**으로 지글(Jiggle)용 컨트롤을 직접 만들어 붙일 수 있습니다.

---

## 1. 설치 및 실행

별도 설치 과정 없이 스크립트 실행만으로 동작합니다.

1. `SecondMotion_v2_6_6.py` 파일을 받습니다.
2. Maya 스크립트 에디터의 **Python 탭**에 아래처럼 실행합니다.

```python
exec(open(r"D:/tools/SecondMotion_v2_6_6.py", encoding="utf-8").read())
```

> 경로는 각자 파일을 둔 위치로 바꿔 주세요. 파일을 열면 마지막 줄(`SecondMotionUI().show()`)이 자동으로 창을 띄웁니다.

**셸프 버튼으로 만들기 (추천):** 위 코드를 셸프에 드래그하면 버튼 한 번으로 실행됩니다.

> 참고: 프리셋은 `<유저폴더>/maya/scripts/sm_presets.json`에 저장됩니다. 처음 실행하면 기본 프리셋이 자동 생성됩니다.

---

## 2. 화면 구성

창은 세 개의 탭으로 나뉩니다.

| 탭 | 용도 |
|---|---|
| **Overlap** | 선택한 컨트롤러에 세컨더리 모션을 베이크 (메인 기능) |
| **VertexMap** | 메쉬 표면에 지글용 컨트롤(스킨 인플루언스)을 생성 |
| **About** | 버전 및 간단 안내 |

---

## 3. Overlap 탭 — 기본 워크플로우

가장 많이 쓰는 핵심 기능입니다. **순서대로** 따라하면 됩니다.

1. 본 애니메이션이 들어간 **컨트롤러를 선택**합니다 (체인이면 부모 1개만 선택해도 됨 → Hierarchy Mode 참고).
2. **Main Operation Mode**에서 어떤 채널을 출렁이게 할지 선택합니다.
3. 슬라이더로 강도/감쇠를 조절합니다.
4. **`APPLY SECOND MOTION`** 버튼을 누릅니다.
5. 결과는 `SM_<컨트롤이름>` 이라는 **애님 레이어**로 생성됩니다. 마음에 안 들면 다시 누르면 같은 레이어가 갱신됩니다.

### Main Operation Mode (상단)

여러 개를 동시에 켤 수 있습니다.

- **Rotation** — 회전축으로 출렁임 (꼬리, 머리카락, 안테나 등 막대형에 적합)
- **Translation** — 위치(이동)로 출렁임
- **Physics** — 관성/오버슈트가 들어간 물리 느낌
- **Custom** — 입력 축 → 출력 축으로 매핑 (아래 Custom Mode 참고)
- **Axis (X / Y / Z)** — 위 모드를 적용할 축을 선택

> **살(flesh)처럼 위아래로 출렁이게 하려면** Rotation이 아니라 **Translation(특히 Y축)** 을 켜야 합니다. 필요하면 Physics를 함께 켜세요.

### 메인 슬라이더

- **Smoothness (Softness)** — 따라오는 지연(딜레이). 값이 클수록 더 늘어지고 부드럽게 따라옴
- **Smoothing** — 결과 커브의 매끄러움 (0.0 ~ 0.95)
- **Scale** — 출렁임의 전체 세기(진폭)
- **Overshoot** — 되돌아올 때 반대로 튕기는 정도 (0.0 ~ 1.0, Physics 느낌 강화)

### Hierarchy / Ignore First

- **Hierarchy Mode** — 켜면 선택한 컨트롤의 **하위 자식들까지 자동 포함**해 체인 전체에 적용 (부모 1개만 선택해도 됨)
- **Ignore First Control** — 선택의 **맨 앞 컨트롤은 제외**. 보통 루트/구동원은 그대로 두고 그 아래만 출렁이게 할 때 사용

---

## 4. Overlap — Advanced Settings

필요할 때만 펼쳐 쓰는 고급 옵션입니다.

### Animation

- **Cycle Mode** — 루프(사이클) 애니메이션용. 시작·끝이 자연스럽게 이어지도록 처리
- **Custom Range** — 체크하면 아래 **Start / End** 프레임 구간만 베이크 (미체크 시 타임라인 전체 범위 사용)

### Chain

- **Decay (Chain Falloff)** — 체인을 따라 내려갈수록 출렁임 세기가 줄어드는 비율 (0.1 ~ 2.0). 1보다 작으면 끝으로 갈수록 약해지고, 1보다 크면 끝이 더 크게 출렁임


### Wind (바람)

- **Enable Wind** 체크 후
- **Wind Strength** (세기), **Wind Direction X / Y / Z** (방향) 설정

### Custom Mode Option

상단에서 **Custom** 모드를 켰을 때만 적용됩니다.

- **Input → Output** : 어떤 축의 움직임을 어떤 축으로 옮길지 매핑 (예: Rotate X → Translate Y)
- **Mapping Gain** : 매핑 강도

### Layer Manager

생성된 `SM_` 레이어를 관리합니다.

- **목록에서 레이어 선택 → Weight %** 슬라이더로 전체 세기 조절 (0 ~ 150%)
- **Refresh** — 목록 새로고침
- **Delete Selected Layer** — 선택한 레이어 삭제
- **Delete ALL** — 모든 `SM_` 레이어 삭제 (확인창 뜸)

> Overlap 탭 상단의 **`DELETE CURRENT VertexMap LAYER`** 버튼은, **씬에서 컨트롤러를 선택한 상태**에서 누르면 그 컨트롤러에 매칭되는 `SM_` 레이어를 바로 지워줍니다.

---

## 5. 프리셋

Overlap 탭 맨 위 **Preset** 영역에서 자주 쓰는 설정을 저장/불러올 수 있습니다.

- 기본 제공: **Natural / Heavy / Bouncy / Whip / Sharp**
- **Save Current** — 현재 슬라이더 값(Softness/Scale/Smoothing/Decay)을 새 프리셋으로 저장
- **Delete Selected** — 사용자 프리셋 삭제 (기본 5종은 삭제 불가)

---

## 6. VertexMap 탭 — 메쉬에 지글 컨트롤 만들기

리깅 컨트롤러가 없는 부위(뱃살, 볼살, 늘어진 천 등)에 출렁임을 주고 싶을 때 사용합니다.
**선택한 버텍스 개수**에 따라 생성 방식이 자동으로 갈립니다.

| 선택 버텍스 | 모드 | 동작 |
|---|---|---|
| **1개** | **Soft** | 중심에서 둥글게 자동 폴오프(소프트 셀렉션처럼) 스킨 웨이트 페인트 |
| **2개 이상** | **Joint** | 조인트형 컨트롤 생성 후 **Paint 버튼으로 직접** 웨이트 페인트 |

### 생성 순서

1. 메쉬에서 출렁이게 할 부위의 **버텍스를 선택**합니다.
2. **Shape** (Cube / Sphere), **Name**(비우면 자동) 지정
3. **Scale**(영향 반경 + 컨트롤 크기), **Weight**(중심 최대 가중치), **Effect**(폴오프 집중도) 조절
4. **FalloffMode** (Volume / Surface), **FalloffCurve** (Smooth / Spline / Linear / Flat) 선택
5. **Orient to World Space** — 컨트롤을 월드 기준으로 정렬할지 여부
6. **`Create`** 버튼 클릭

### 생성 후

- 슬라이더(**Scale / Weight / Effect / Falloff**)는 목록에서 항목을 선택하면 **실시간 반영**됩니다.
  - Scale: 드래그하는 즉시 컨트롤 크기/반경 변경
  - Weight·Effect·Falloff: 릴리즈 시 둥근 폴오프를 다시 페인트
- **Joint 모드**는 **Paint** / **Smooth** / **⚙(옵션)** 버튼으로 직접 웨이트를 칠합니다.
- 하단 목록에서 우클릭 또는 버튼으로 **Select / Delete / Refresh** 가능.

### 그리고 → 출렁임 베이크

VertexMap으로 만든 **컨트롤(스피어/큐브)을 선택**한 뒤 **Overlap 탭에서 `APPLY`** 하면, 몸의 움직임을 따라 지글(Jiggle)이 베이크됩니다.

> 생성된 노드는 `SecondMotion_GRP > VertexMap_GRP > <모델명>_VM_GRP` 계층으로 정리됩니다.
> 컨트롤(스피어/큐브)을 아웃라이너에서 직접 지워도 연관 노드(JNT/OFFSET/CTRL/제약 등)가 함께 정리됩니다. 빈 그룹도 자동 삭제됩니다.

---

## 7. 자주 쓰는 시나리오 정리

- **꼬리·머리카락·안테나 출렁임** → Overlap, Rotation 켜고 Hierarchy Mode로 체인 전체 적용, Decay로 끝쪽 감쇠
- **뱃살·볼살이 위아래로 출렁** → Overlap, **Translation Y** (필요 시 Physics) — Rotation 아님 주의
- **루프 사이클 애니** → Advanced > Animation > **Cycle Mode** 체크
- **리그 컨트롤 없는 부위** → VertexMap으로 컨트롤 생성 → Overlap에서 Apply

---

## 8. 참고 / 주의

- 잠겨 있거나 키 입력 불가(non-keyable)한 채널은 자동으로 건너뜁니다.
- APPLY는 한 번의 Undo 청크로 묶이므로 **Ctrl+Z 한 번**으로 되돌릴 수 있습니다.
- 같은 컨트롤에 다시 APPLY하면 기존 `SM_` 레이어를 삭제 후 재생성하므로 레이어가 중첩 누적되지 않습니다.
- 진행 중 **Esc**로 베이크를 취소할 수 있습니다.
