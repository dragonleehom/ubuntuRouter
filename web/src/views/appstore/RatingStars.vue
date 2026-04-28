<template>
  <div
    class="rating-stars"
    :class="[readonly ? 'readonly' : 'interactive', sizeClass]"
  >
    <span
      v-for="star in 5"
      :key="star"
      class="star"
      :class="{
        filled: star <= displayValue,
        half: !filledOnly && star - 0.5 === displayValue,
        hovered: !readonly && star <= hoverValue,
        active: !readonly && star <= modelValue,
      }"
      @click="!readonly && $emit('update:modelValue', star)"
      @mouseenter="!readonly && (hoverValue = star)"
      @mouseleave="!readonly && (hoverValue = 0)"
    >
      <el-icon v-if="star <= displayValue" :size="iconSize"><StarFilled /></el-icon>
      <el-icon v-else :size="iconSize"><Star /></el-icon>
    </span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { StarFilled, Star } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Number,
    default: 0,
  },
  readonly: {
    type: Boolean,
    default: false,
  },
  size: {
    type: String,
    default: 'default', // 'small', 'default', 'large'
  },
})

defineEmits(['update:modelValue'])

const hoverValue = ref(0)

const displayValue = computed(() => {
  if (!props.readonly && hoverValue.value > 0) return hoverValue.value
  return props.modelValue
})

const filledOnly = computed(() => Number.isInteger(displayValue.value))

const iconSize = computed(() => {
  switch (props.size) {
    case 'small': return 14
    case 'large': return 28
    default: return 20
  }
})

const sizeClass = computed(() => `size-${props.size}`)
</script>

<style scoped>
.rating-stars {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.rating-stars.interactive {
  cursor: pointer;
}

.star {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s, color 0.15s;
  color: #d3d3d3;
}

.star.filled {
  color: #f7ba2a;
}

.star.half {
  position: relative;
  color: #f7ba2a;
}

.interactive .star:hover {
  transform: scale(1.15);
}

.interactive .star.hovered {
  color: #f7ba2a;
}

.interactive .star.active {
  color: #f7ba2a;
}
</style>
