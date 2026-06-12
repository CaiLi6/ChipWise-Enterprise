import { defineStore } from 'pinia'
import { ref } from 'vue'
import { compareChips, listChips } from '@/api/compare'
import type { ChipListItem, CompareResult } from '@/types/api'

// ---------------------------------------------------------------------------
// Compare store
//
// CompareView previously kept all of its state (selected chips, the compare
// result, view toggles) in component-local refs. Vue Router unmounts the view
// when the user navigates to another page, so those refs were destroyed and the
// result vanished on return. Hoisting the state into a Pinia store keeps it
// alive for the lifetime of the app, so switching pages and coming back shows
// the previous comparison intact.
// ---------------------------------------------------------------------------
export const useCompareStore = defineStore('compare', () => {
  const allChips = ref<ChipListItem[]>([])
  const searchKeyword = ref('')
  const searching = ref(false)
  const selectedChips = ref<string[]>([])
  const result = ref<CompareResult | null>(null)
  const loading = ref(false)
  const highlightDiff = ref(true)
  const groupByCategory = ref(true)
  const dimensionFilter = ref<string[]>([])

  async function loadChips(q?: string): Promise<void> {
    searching.value = true
    try {
      const resp = await listChips(q, 50)
      allChips.value = resp.chips
    } finally {
      searching.value = false
    }
  }

  async function runCompare(): Promise<void> {
    loading.value = true
    try {
      result.value = await compareChips({
        chip_names: [...selectedChips.value],
        dimensions: dimensionFilter.value.length ? [...dimensionFilter.value] : undefined,
      })
    } finally {
      loading.value = false
    }
  }

  function removeChip(chip: string): void {
    selectedChips.value = selectedChips.value.filter((c) => c !== chip)
    if (!result.value) return
    result.value.chips = result.value.chips.filter((c) => c !== chip)
    for (const k of Object.keys(result.value.comparison_table)) {
      delete result.value.comparison_table[k][chip]
    }
    if (result.value.chips.length < 2) {
      result.value = null
    }
  }

  return {
    allChips,
    searchKeyword,
    searching,
    selectedChips,
    result,
    loading,
    highlightDiff,
    groupByCategory,
    dimensionFilter,
    loadChips,
    runCompare,
    removeChip,
  }
})
