import { useState, useEffect, useCallback, useRef } from "react";
import { TimelineSlice } from "../api/types";

export function useTimelineSlider(timeline: TimelineSlice[] = [], autoPlayInterval: number = 1500) {
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const timerRef = useRef<any>(null);

  const maxSteps = timeline.length > 0 ? timeline.length - 1 : 0;
  const currentSlice = timeline[currentStep] || null;

  const nextStep = useCallback(() => {
    setCurrentStep((prev) => (prev >= maxSteps ? 0 : prev + 1));
  }, [maxSteps]);

  const prevStep = useCallback(() => {
    setCurrentStep((prev) => (prev <= 0 ? maxSteps : prev - 1));
  }, [maxSteps]);

  const togglePlay = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  useEffect(() => {
    if (isPlaying && maxSteps > 0) {
      timerRef.current = setInterval(nextStep, autoPlayInterval);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, maxSteps, autoPlayInterval, nextStep]);

  return {
    currentStep,
    setCurrentStep,
    currentSlice,
    maxSteps,
    isPlaying,
    togglePlay,
    nextStep,
    prevStep,
  };
}
