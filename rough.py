import heapq
class Solution:
    def minimumEffortPath(self, heights: list[list[int]]) -> int:
        rows, cols = len(heights), len(heights[0])
        min_eff = {}
        for y in range(len(heights)):
            for x in range(len(heights[y])):
                min_eff[(x,y)] == float('inf')

        min_eff[(0,0)] = 0
        min_heap = [(0,0,0)]
        while min_heap:
            curr_eff, x, y = heapq.heappop(min_heap)

            if min_eff[(x,y)] < curr_eff:
                continue
            
            if (x,y) == (len(heights)-1, len(heights[0])-1):
                return curr_eff
                
            
            for a,b in [(x+1,y),(x-1,y), (x, y+1), (x, y-1)]:
                if a >= 0 and a <= len(heights) and b >= 0 and b <= len(heights[0]):
                    diff = abs(heights[a][b] - heights[x][y])
                    eff_curr = max(curr_eff, diff)
                    if eff_curr < min_eff[a][b]:
                        min_dis[(a,b)] = curr_dist
                        heapq.heappush(min_heap, (dist_calc, (a,b), heights[a][b] - heights[x][y]))
                    