#!/bin/bash
# Demonstration of checkpoint functionality

echo "======================================================================"
echo "CHECKPOINT DEMONSTRATION"
echo "======================================================================"
echo ""
echo "This demo will:"
echo "1. Simulate an interrupted extraction (1 page only)"
echo "2. Verify the checkpoint was created"
echo "3. Show you how to resume"
echo ""
echo "Press Enter to continue..."
read

# Step 1: Simulate interruption
echo ""
echo "======================================================================"
echo "STEP 1: Simulating interrupted extraction"
echo "======================================================================"
uv run python simulate_interrupt.py

# Step 2: Verify checkpoint
echo ""
echo "======================================================================"
echo "STEP 2: Verifying checkpoint structure"
echo "======================================================================"
uv run python test_checkpoint.py

# Step 3: Instructions
echo ""
echo "======================================================================"
echo "STEP 3: Resume extraction"
echo "======================================================================"
echo ""
echo "The checkpoint has been created and validated!"
echo ""
echo "To resume the extraction, run:"
echo "  uv run pdf-extractor extract test_sample.pdf"
echo ""
echo "When prompted 'Resume from checkpoint? [Y/n]:', press Y"
echo ""
echo "The extraction will continue from page 2 (skipping already-processed page 1)"
echo ""
echo "======================================================================"
echo "CHECKPOINT FILES"
echo "======================================================================"
echo ""
echo "Checkpoint location: output/.checkpoint.json"
echo "Checkpoint size: $(du -h output/.checkpoint.json | cut -f1)"
echo ""
echo "To view checkpoint:"
echo "  cat output/.checkpoint.json | jq ."
echo ""
echo "To force a fresh start (ignore checkpoint):"
echo "  uv run pdf-extractor extract test_sample.pdf --force-restart"
echo ""
echo "To disable checkpointing:"
echo "  uv run pdf-extractor extract test_sample.pdf --no-checkpoint"
echo ""
