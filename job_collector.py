"""
Compatibility wrapper for the refactored job_collector package.
This file maintains backward compatibility with existing scripts.
"""

# Import the main function from the new structure
from main import main

if __name__ == "__main__":
    main()


需要注意：
在dashboard design时需要理解我的需求：
1. 能清楚看到每天的岗位变化。把刷屏中介单独摆开（IT 外包/培训, 聚合站, 外包），但是需要注意不能排除掉岗位多的正常公司
2. 但是有时候一天会抓取太多的岗位，我没办法一个个看，除了 Dashboard 体现岗位变化以外，我还有个需求是如何把大中公司的岗位摆在前面让我有先看到？大中公司可能会有很多个维度：知名度、赚钱能力、声誉、公司人数等。如果dashboard 没办法解决这个需求，帮我设计一种方式来解决我这个需求）。

总体架构：你来编排总体流程，给 subagent prompt. PM & design subagent (理解发掘需求，设计合理的方法解决这个需求) -> 两个 Subagent 来评估，评估通过后给engieer(写代码解决这个pm提出的方法)，不通过的话回到 PM & design subagent

不停迭代（提出design -> evaluate -> implement -> design -> ...）.loop 完成后写个 summary report 来描述这个 loop 里面发生的情况（你的 design, subagent 的 evluation, 如何改进；最终 dashboard 描述）。