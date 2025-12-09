# Checkpoint Resume Workflow Test

## Manual Test Procedure

This document describes how to manually test the checkpoint resume functionality.

### Prerequisites
- `test_sample.pdf` (3 pages)
- Clean `output/` directory

### Test 1: Basic Resume

1. **Start extraction and interrupt:**
   ```bash
   # Clean output directory
   rm -rf output/*

   # Start extraction
   uv run pdf-extractor extract test_sample.pdf

   # Let it process 1 page, then press Ctrl+C to interrupt
   ```

2. **Verify checkpoint exists:**
   ```bash
   ls -la output/.checkpoint.json
   uv run python test_checkpoint.py
   ```

3. **Resume extraction:**
   ```bash
   uv run pdf-extractor extract test_sample.pdf
   # When prompted "Resume from checkpoint? [Y/n]:", press Y
   ```

4. **Verify:**
   - Extraction starts from page 2 (not page 1)
   - All 3 pages are processed total
   - Checkpoint is deleted after completion
   - Final output contains all Q&As

### Test 2: Force Restart

1. **With existing checkpoint:**
   ```bash
   # Create a checkpoint by running simulate_interrupt.py
   uv run python simulate_interrupt.py

   # Force restart (ignore checkpoint)
   uv run pdf-extractor extract test_sample.pdf --force-restart
   ```

2. **Verify:**
   - No resume prompt shown
   - Extraction starts from page 1
   - All pages processed
   - Old checkpoint overwritten

### Test 3: Decline Resume

1. **With existing checkpoint:**
   ```bash
   # Create checkpoint
   uv run python simulate_interrupt.py

   # Start extraction
   uv run pdf-extractor extract test_sample.pdf
   # When prompted, press 'n' to decline resume
   ```

2. **Verify:**
   - Extraction starts from page 1 (fresh start)
   - Checkpoint deleted
   - New checkpoint created as pages are processed

### Test 4: No Checkpoint Mode

1. **Disable checkpointing:**
   ```bash
   rm -rf output/*
   uv run pdf-extractor extract test_sample.pdf --no-checkpoint
   ```

2. **Verify:**
   - No `.checkpoint.json` file created
   - Extraction completes normally
   - Output files created as usual

3. **Interrupt and restart:**
   ```bash
   # Start with --no-checkpoint
   uv run pdf-extractor extract test_sample.pdf --no-checkpoint
   # Press Ctrl+C after 1 page

   # Restart
   uv run pdf-extractor extract test_sample.pdf --no-checkpoint
   ```

4. **Verify:**
   - No resume prompt (no checkpoint)
   - Starts from page 1 again

### Test 5: Wrong PDF Detection

1. **Create checkpoint for one PDF:**
   ```bash
   uv run python simulate_interrupt.py  # Uses test_sample.pdf
   ```

2. **Try to resume with different PDF:**
   ```bash
   uv run pdf-extractor extract test_crossref.pdf
   ```

3. **Verify:**
   - Warning shown: "Checkpoint is for a different PDF"
   - Checkpoint ignored
   - Extraction starts from page 1

### Test 6: Large PDF (Real-world Scenario)

1. **Process large PDF with checkpoints:**
   ```bash
   uv run pdf-extractor extract Convex_Optimization_Solutions.pdf
   # Let it run for a few pages (5-10)
   # Press Ctrl+C to interrupt
   ```

2. **Verify checkpoint:**
   ```bash
   uv run python test_checkpoint.py
   # Should show progress (e.g., "5/200+ pages")
   ```

3. **Resume:**
   ```bash
   uv run pdf-extractor extract Convex_Optimization_Solutions.pdf
   # Press Y to resume
   # Let it process a few more pages
   # Can interrupt and resume multiple times
   ```

## Expected Results

All tests should pass with:
- ✅ Checkpoint created after each page
- ✅ Valid JSON structure
- ✅ Resume prompt shows correct progress
- ✅ Extraction continues from correct page
- ✅ No duplicate processing
- ✅ Checkpoint deleted on completion
- ✅ All flags work as documented

## Common Issues

### Issue: Resume doesn't work
- **Check:** Does `output/.checkpoint.json` exist?
- **Check:** Is the PDF path correct (absolute vs relative)?
- **Fix:** Use `--force-restart` to start fresh

### Issue: Extraction starts from page 1 even with checkpoint
- **Check:** Did you answer 'n' to resume prompt?
- **Check:** Is checkpoint for the same PDF?
- **Fix:** Answer 'Y' to resume prompt

### Issue: Checkpoint not being deleted
- **Check:** Did extraction complete successfully?
- **Check:** Were there any errors during processing?
- **Fix:** Manually delete with `rm output/.checkpoint.json`

## Success Criteria

✅ All 6 manual tests pass
✅ No data loss on interruption
✅ Resume works correctly across multiple interruptions
✅ Checkpoint overhead is minimal (<1% performance impact)
✅ Error messages are clear and helpful
