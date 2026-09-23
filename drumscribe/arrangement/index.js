// Public entry point for DrumScribe arrangement/off-vocal structure analysis.
// Import from this file so the implementation can evolve without changing callers.
export {
  analyzeSections,
  extractSectionFeatures,
} from './section-analysis.js';

export {
  rescoreKstByArrangement,
  arrangementKstPolicyV39D,
  arrangementKstPolicyV46R1,
} from './kst-rescore.js';

export {
  rescoreHatArticulationByArrangement,
  arrangementHatPolicyV1,
} from './hat-rescore.js';
