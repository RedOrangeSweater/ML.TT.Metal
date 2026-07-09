# Build matching `ttnn-shutov` from Merge-pin tt-metal (`8dfb324`)

## One-liner

Public PyPI never shipped a `ttnn` wheel for the green-CI tt-metal pin used by
the eager `pytorch2.0_ttnn` stack (`8dfb324099a`). This branch builds that wheel
from source (manylinux + cibuildwheel) and publishes it as
`ttnn-shutov==0.65.0.dev20251204+g8dfb324099` so Eager Execution can share one
ABI with `torch-ttnn-shutov` built against the same commit.

## Why

1. Eager path passes Python `ttnn` Device objects into the C++ extension
   (`as_torch_device`). Different tt-metal lines → layout / symbol mismatch.
2. SONAME isolation only fixes extension *load*; it does not make Device/Tensor
   safe across ABI lines.
3. Internal index has no artifact whose filename embeds `8dfb324`. Exact pin
   requires from-source build.
4. This simulates the cross-team handoff that would have followed Merge of the
   build-fix PR: matching runtime wheel on a public index.

## How

| Step | Detail |
| --- | --- |
| Checkout | `8dfb324099a` (+ submodules) |
| Image | `dockerfile/Dockerfile.manylinux` (no TT harbor) |
| Build | `cibuildwheel` `cp310-manylinux_x86_64`, test=`import ttnn` |
| Repack | `tools/repack_ttnn_shutov_wheel.py` → Name `ttnn-shutov` |
| Version | `0.65.0.dev20251204+g8dfb324099` (line + exact SHA) |
| Default CI | `publish_target=none` (artifact only) |

Workflow: `.github/workflows/release-ttnn-shutov-from-source.yaml`.

## Success criteria

- Artifact wheel installs: `import ttnn` OK.
- Paired with `torch-ttnn-shutov` built on the same pin: `from torch_ttnn.cpp_extension import ttnn_module` OK (verified in the pytorch fork).
- TestPyPI then prod: same version string; only `--index-url` differs.

## Non-goals

- Not publishing under upstream name `ttnn` (Tenstorrent-owned).
- Not claiming on-device eager correctness in this metal-only PR (HW evidence lives with the pytorch packaging PR).
- Not using Tenstorrent private runners / harbor (unavailable on this fork).

## Publish order

1. This workflow → TestPyPI (`publish_target=testpypi`).
2. `torch-ttnn-shutov` release against the matching pin → TestPyPI.
3. Same buttons with `publish_target=pypi` from the showcase remote that owns prod credentials.
