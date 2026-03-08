from a3s_code import Agent

agent = Agent.create("test/all_config.hcl")
session = agent.session(r"D:\project\safety\SafeClaw", permissive=True)

result = session.send("使用explain-code skills分析下本项目如何工作的")
print(result.text)
