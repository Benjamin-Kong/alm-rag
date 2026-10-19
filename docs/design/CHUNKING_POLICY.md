# Chunk 크기, 임베딩 예산 및 완전한 Item 복원 (v0.2 Draft)

## 1. 핵심 원칙
- **원본 보존 용량과 Vector 입력 크기는 분리**한다. 모든 Field/원본 Wiki·HTML/Table JSON/Revision/첨부 메타데이터는 SQLite+로컬 파일에 보존한다. 임베딩을 1 Item = 1 Vector로 제한하지 않는다.
- `item_uid`는 1:N Chunk와 연결하며 Retrieval은 Chunk 후보를 fusion 후 Item 고유 ID로 그룹화한다. 필요하면 Item 전체를 SQLite로 복원한다. 다른 Item을 Chunk 내부에 임의로 섞지 않는다.
- **텍스트 임베딩만** 대상으로 한다. EmbeddingGemma 2의 이미지/오디오 기능과 첨부파일 임베딩은 이번 버전 범위 외(Q02).

## 2. 설정과 초기값 (튜닝 가능한 제안값, 모델 스펙 보장 아님)
| 키 | 초기값 | 설명 |
|---|---|---|
| `target_chunk_tokens` | 512 | 의미 단락과 표 행을 우선해 가까운 크기로 구성 |
| `max_chunk_tokens` | 1024 | 원자적 의미 경계를 깨지 않는 범위에서 최대 입력 길이 제한 |
| `overlap_tokens` | 64 | Description의 인접 문단 분할 시만 사용; Table은 헤더 반복, Custom Field는 일반적으로 0 |
| `reserved_context_tokens` | 128 | Title/Field label/Table header/instruction prefix를 위한 예약량 |
| `min_chunk_tokens` | 64 | 문맥 손상 없는 경우에만 소형 Chunk 병합; 단일 짧은 필드는 단독 허용 |
| `oversize_behavior` | `SPLIT_OR_FAIL` | 자동 자르기 금지, 분할 실패 시 Item 신규 판 게시 보류 |
| `tokenizer_mode` | `AUTO_MATCH_MODEL` | 실제 Ollama 모델 입력 토큰 계수 비교가 가능한 tokenizer 우선 |

## 3. 실제 모델 한계
Google EmbeddingGemma 2 설명에는 8,192-token context 및 768-d vector가 명시되지만 Ollama 배포 페이지가 별도 최대 context 수치를 표기할 수 있다. 실제 런타임 model tag/digest/num_ctx/truncation/API 동작을 검증하고 `effective_max_input_tokens`를 명시적으로 설정한다. 기본값 1,024는 안전/검색 품질/성능을 위한 보수적 설계안이다.

`len(exact_embedding_input_tokens) <= min(config.max_chunk_tokens, effective_max_input_tokens - safety_margin)`을 강제한다. Title과 필드 라벨·prefix 및 표 헤더 **포함**해서 제한을 계산한다. 토큰 계수 검증 불가하면 보수적 byte/char 측정만으로 안전을 단정하지 말고 임베딩 API 거부/잘림을 탐지해 FAIL로 처리한다. 서버 설정이 자동 truncation이면 비활성화하거나 추적 가능한 결과 확인 메커니즘을 마련한다.

## 4. 의미 경계별 알고리즘
1. Block 순서 유지: Header → paragraph/list → Table → Custom field를 구분, Section Heading 및 Field Label을 각 Chunk 컨텍스트에 포함한다.
2. Text: 문장/문단 단위로 Packing; 한 문장이 max 초과면 문장 내부 구문/토큰 경계로 재분할, 정확한 source offset과 source text span 보존.
3. Table: Header 계층과 행 식별자를 모든 행 그룹 Chunk에 반복. Header-Value 관계 상실 금지. 한 행이 너무 길면 셀별 하위 분할 및 row_id에 연결, 검증 불가능하면 FAILED.
4. Custom Field: 단일 Field가 범위 내면 단독 Chunk, 과대 Text Field는 Description과 동일 분할. Scalar/Choice Field는 원본 Raw Value 보존과 임베딩 대상 선택에 따름.
5. Changed Chunk에 대해서만 embed API 재호출. `content_hash`는 Title, Field label, 직렬화된 내용, instruction/prefix와 Chunker/Model version 포함.

## 5. 테스트와 운영 지표
- 100, 1,024, 8,000, 15,000 token 문장/표/혼합 Item fixture.
- 정확한 Text byte/offset 및 모든 Source Table cell의 coverage 검증; 버려진 구간 0.
- 각 Chunk `input_tokens`, `content_hash`, `item_uid`, `field_def_uid`, `row_ids` 저장.
- 측정 지표: Chunk/Item 분포 P50/P95/Max, truncation_count (항상 0), oversize_failed_count, 토큰 낭비율, 변경 대비 재임베딩률, Retrieval Recall@K.
- 조정 시 configuration fingerprint로 인덱스 세대 전환 필요성을 판단하고 인덱스 혼합 금지.

**참고:** https://registry.ollama.com/library/embeddinggemma-2
