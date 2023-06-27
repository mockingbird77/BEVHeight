def findKthLargest(self, nums: List[int], k: int) -> int:
    # 1、堆排序手写实现 
    #    小顶堆  第k大、前k大建小顶堆；第k小、前k小建大顶堆
    def heapify(tree, n, i):
        c1, c2 = 2 * i + 1, 2 * i + 2
        min_idx = i
        if c1 < n and tree[c1] < tree[min_idx]:
            min_idx = c1
        if c2 < n and tree[c2] < tree[min_idx]:
            min_idx = c2
        if min_idx != i:
            tree[i], tree[min_idx] = tree[min_idx], tree[i]
            heapify(tree, n, min_idx)
    def build_heap(tree, n):
        last_node = n - 1
        parent = (last_node - 1) // 2
        for i in range(parent, -1, -1):
            heapify(tree, n, i)
    hp = nums[:k]
    build_heap(hp, k)
    for i in range(k, len(nums)):
        if nums[i] > hp[0]:
            hp[0] = nums[i]
            heapify(hp, k, 0)
    return hp[0]
    
    # 2、堆排序掉包实现
    #    第k大、前k大建小顶堆；第k小、前k小建大顶堆
    hp = nums[:k]
    heapq.heapify(hp)  # 建堆
    # 遍历k后面的树 如果发现比堆顶元素大 那么就把堆顶元素换掉
    for i in range(k, len(nums)):
        # 小顶堆最终保存前k大的数  
        if nums[i] > hp[0]:
            heapq.heappop(hp)  # pop出堆顶元素 堆还是维护小顶堆
            heapq.heappush(hp, nums[i])  # push进一个元素 堆还是维护小顶堆
    return hp[0]
