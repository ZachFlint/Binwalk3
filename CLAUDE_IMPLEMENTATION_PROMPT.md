# Implementation Prompt for Binwalk3 Package

Please implement the binwalk3 Python package according to the detailed plan in `IMPLEMENTATION_PLAN.md`.

## Your Task

Work through the implementation plan **one checkbox at a time**, following these rules:

### Working Method

1. **Read the plan**: Open `D:\Binwalk3\IMPLEMENTATION_PLAN.md`
2. **One task at a time**: Complete each checkbox task sequentially
3. **Mark complete**: After completing each task, edit `IMPLEMENTATION_PLAN.md` and change `- [ ]` to `- [x]` for that specific item
4. **Verify before proceeding**: Test that each task works before moving to the next
5. **Follow the order**: Complete phases and tasks in the exact order listed

### Critical Requirements

- **Production-ready code only**: Every line of code must be fully functional, no placeholders or TODOs
- **Test as you go**: Run tests after each phase to catch issues early
- **Commit regularly**: Make git commits at the end of each phase as specified in the plan
- **Windows platform**: All commands and paths are for Windows - use PowerShell/CMD syntax
- **No skipping**: Every checkbox must be completed, no exceptions

### Project Context

**What you're building**: A Python package that provides binwalk v2's API while using the faster binwalk v3 Rust binary under the hood.

**Key facts**:
- **PyPI name**: `binwalk3` (the package name on PyPI)
- **Import name**: `binwalk` (users will `import binwalk` just like v2)
- **Location**: `D:\Binwalk3`
- **Binary**: Bundle pre-compiled Windows x64 binwalk v3 binary
- **API**: 100% compatible with binwalk v2 Python API

### Expected Workflow Example

```
1. Read Phase 1, Task 1.1, first checkbox
2. Execute: Navigate to D:\Binwalk3
3. Mark complete: Change line to `- [x] Navigate to D:\Binwalk3 directory`
4. Read next checkbox
5. Execute: git init
6. Mark complete: Change line to `- [x] Initialize Git repository: git init`
7. Continue...
```

### When You Encounter Issues

- **Build errors**: Read error messages carefully, search for solutions
- **Missing dependencies**: Install them before proceeding
- **Test failures**: Fix the code, don't skip the test
- **Unclear instructions**: Ask for clarification before proceeding

### Success Criteria

The implementation is complete when:
- All checkboxes in all 11 phases are marked `[x]`
- All tests pass
- Package builds without errors
- Package is published to PyPI
- `pip install binwalk3` works and provides the v2 API

### Start Here

Begin with **Phase 1: Project Setup & Structure** and work through each checkbox systematically.

Remember: **One task at a time. Mark complete. Move forward.**

Good luck!
