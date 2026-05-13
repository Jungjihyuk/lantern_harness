# Known Issues — 알아두고 점진 개선해야 할 사안

> 시스템 동작에 본질적 문제는 아니지만, 인지 부담 / framing 일관성 측면에서 정직히 기록해두는 사안 모음.
> 즉시 fix 가 아닌 **점진적으로 해소되는** 항목들. 각 항목은 자연 해소 경로 또는 후속 작업 계획을 포함.

관련 이슈: [#10](https://github.com/Jungjihyuk/lantern_harness/issues/10) (이 문서의 출처), [#6](https://github.com/Jungjihyuk/lantern_harness/issues/6) (v2 cutover), [#7](https://github.com/Jungjihyuk/lantern_harness/issues/7) (v1 명령 v2 재정의)

---

## 1. `standard/` 의 추상화 층위 혼종

### 현황
`standard/` 한 폴더 안에 **2가지 성격이 다른 것들**이 평면적으로 섞여 있다:

| 분류 | 항목 | 성격 |
|---|---|---|
| **자산 (artifact)** | `instructions/`, `hooks/`, `adapters/`, `workflows/`, `evals/` 등 7 메커니즘 폴더 | `manifest.yaml` 가진 실제 운영 자산 |
| **schema 정의** | `roles.yaml` | 도메인별 허용 role enum — 검증 기준 |

### 왜 문제인가
처음 보는 사람이 `standard/` 를 열었을 때 "이게 정확히 무엇들의 모음인지" 한눈에 잡히지 않음.
- 7 메커니즘 폴더는 *artifact 컨테이너* 인데,
- `roles.yaml` 은 *schema* — 층위가 다름

### 향후 방향 (옵션, 우선순위 낮음)
schema 파일을 `_schema/` 같은 별도 위치로 분리하면 층위가 명확해질 수 있음. 단 cosmetic 변경이므로 다른 개선과 함께 묶을 때 검토.

### 진행 이력
- 2026-05-13: 죽은 메타 파일 `standard_meta.yaml` (코드 미참조, plugins 필드 일관성 깨짐) 제거 — 3 층위 → 2 층위로 축소.

---

## 2. Framing vs 실 내용 미스매치 — **해소됨 (2026-05-13)**

### 현황 (당시)
초기 framing 은 "커뮤니티가 검증한 공인 토대" 였지만 실 내용은 skeleton/결합 코드라 신뢰 gap 이 있었다.

### 적용된 정의
- **standard** = 도구/도메인 중립의 **검증된 하네스 기본 구성** (시간 따라 합의가 쌓임)
- **know-how** = **실험적 하네스** 또는 **프로젝트 성격이 묻어나는 자산** (override 포함)

### 갱신 대상 (완료)
- [README.md](../README.md) §"Lantern Harness란?" + "왜 만들었나" 표
- [system-essence.md](system-essence.md) §8
- [standard/README.md](../standard/README.md) 상단

### 남은 항목 (별도 issue 로 추적)
- `hooks/` skeleton → #6 후속에서 채워짐
- `evals/cases/` v1 형식 → #7 후속에서 v2 적응

---

## 3. `adapters/` 분류의 모호함 — **해소됨 (2026-05-13)**

### 현황 (당시)
`adapters/` 는 7 메커니즘 폴더 중 하나였지만, 그 안에 (a) provider artifact (`claude/`, `codex/`) 와 (b) 엔진 .py 7개 (`base.py`, `registry.py`, `_mutation.py`, `enable.py`, `disable.py`, `list.py`, `show.py`) 가 한 평면에 섞여 있었음. 다른 6 메커니즘은 자산만 두고 엔진은 `lib/` 에 있어서 형평성 깨짐.

### 적용된 조치
- 엔진 .py 7개를 `lib/adapters/` 로 이동. import 를 절대 경로 (`from lib.adapters.base import ...`) 로 갱신.
- `standard/adapters/` 는 provider artifact (claude/, codex/) 만 남김 — 다른 메커니즘과 동일 패턴.
- `bin/cmd/{enable,disable,show,list}.sh` 가 `PYTHONPATH=$HARNESS_HOME python3 -m lib.adapters.X` 로 호출.
- `registry.py` 의 `_ADAPTERS_DIR` 은 `HARNESS_HOME` env var 기반으로 보정.
- `omo/` placeholder 제거 (registry.yaml / link.sh / 문서 4곳 청소 포함).

### 남은 framing
adapters 는 여전히 "외부 결합 layer" 라는 다른 성격. `standard/adapters/README.md` 상단에 명시 — AIMA 의 actuator (외부 호출) 쪽, percept 는 `cognition.context` 가 담당.

---

## 자연 해소 예정 항목

다음 항목들은 별도 작업 없이 후속 이슈 진행과 함께 자연 해소된다:

- **hooks/ skeleton 문제** → [#6](https://github.com/Jungjihyuk/lantern_harness/issues/6) 후속에서 hook logic 채워지면 해소
- **evals/cases/ v1 형식** → [#7](https://github.com/Jungjihyuk/lantern_harness/issues/7) 에서 v2 적응되면 해소

---

## 우선순위

**낮음.** 즉시 fix 안 해도 시스템 동작과 무관. 단 framing 조정 / 문서 정리는 작업량이 작아 가능한 시점에 점진 적용.

## Todo 추적

이 문서의 진단 항목을 실제 적용으로 옮기는 작업은 [#10](https://github.com/Jungjihyuk/lantern_harness/issues/10) 의 Todo 체크리스트에서 추적한다.
