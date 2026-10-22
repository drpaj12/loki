module ctrl_ports(input clk, input rst, input arst, input en, input sel, input [3:0] d0, input [3:0] d1,
                  input g, output [3:0] q_mux, output reg [3:0] q_e, output reg [3:0] q_a,
                  output reg [3:0] q_s, output reg [3:0] q_l);
  assign q_mux = sel ? d0 : d1;
  always @(posedge clk) if (en) q_e <= d0;
  always @(posedge clk or posedge arst) if (arst) q_a <= 4'd0; else q_a <= d1;
  always @(posedge clk) if (rst) q_s <= 4'd0; else q_s <= d0;
  always @* if (g) q_l = d1;
endmodule
