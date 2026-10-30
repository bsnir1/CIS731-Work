import csv
import glob
import os

def calculate_corpus_stats():
    total_notes = 0
    total_duration_s = 0.0
    gap_threshold = 0.1
    phrase_boundaries = 0
    
    # Process all A1 files
    csv_files = glob.glob("vocadito/Annotations/Notes/*_notesA1.csv")
    
    if not csv_files:
        print("No CSV files found in vocadito/Annotations/Notes/")
        return
        
    for filepath in csv_files:
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            notes = []
            
            for row in reader:
                if not row: continue
                # onset, frequency, duration
                onset = float(row[0])
                duration = float(row[2])
                notes.append({'onset': onset, 'duration': duration})
                
                total_notes += 1
                
            # Add up duration for the whole clip
            if notes:
                clip_duration = (notes[-1]['onset'] + notes[-1]['duration']) - notes[0]['onset']
                total_duration_s += clip_duration
                
            # Count gaps
            for i in range(1, len(notes)):
                prev_end = notes[i-1]['onset'] + notes[i-1]['duration']
                curr_start = notes[i]['onset']
                if (curr_start - prev_end) > gap_threshold:
                    phrase_boundaries += 1
                    
    avg_sec_per_note = total_duration_s / total_notes
    avg_window_12 = avg_sec_per_note * 12
    
    print(f"Total Notes (A1): {total_notes}")
    print(f"Total Duration (s): {total_duration_s:.2f}")
    print(f"Average seconds per note: {avg_sec_per_note:.3f} s")
    print(f"Average 12-note window duration: {avg_window_12:.2f} s")
    print(f"Phrase Boundaries (gap > {gap_threshold}s): {phrase_boundaries}")
    print(f"Total Phrase Chunks: {phrase_boundaries + len(csv_files)}") # boundaries + 1 chunk per clip

if __name__ == '__main__':
    calculate_corpus_stats()
