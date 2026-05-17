import { create } from "zustand";

type FilterState = {
  globalSearch: string;
  category: string;
  selectionStatus: string;
  qualityLevel: string;
  setGlobalSearch: (value: string) => void;
  setCategory: (value: string) => void;
  setSelectionStatus: (value: string) => void;
  setQualityLevel: (value: string) => void;
  reset: () => void;
};

export const useFilterStore = create<FilterState>((set) => ({
  globalSearch: "",
  category: "",
  selectionStatus: "",
  qualityLevel: "",
  setGlobalSearch: (value) => set({ globalSearch: value }),
  setCategory: (value) => set({ category: value }),
  setSelectionStatus: (value) => set({ selectionStatus: value }),
  setQualityLevel: (value) => set({ qualityLevel: value }),
  reset: () => set({ globalSearch: "", category: "", selectionStatus: "", qualityLevel: "" })
}));

