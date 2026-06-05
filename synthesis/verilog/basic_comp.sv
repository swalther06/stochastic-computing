module mux #(parameter W = 4) (input sel, input [W-1:0] a, input [W-1:0] b, output reg [W-1:0] y);
    always_comb y = sel ? b : a;
endmodule

module dff #(parameter W = 4) (input clk, rst, input [W-1:0] d, output reg [W-1:0] q);
    always_ff @(posedge clk) begin
        if (rst) q <= 0;
        else     q <= d;
    end
endmodule

module ctr #(parameter W = 4) (
    input              clk, rst,
    output reg [W-1:0] count
);
    always_ff @(posedge clk) begin
        if (rst) count <= 0;
        else     count <= count + 1;
    end
endmodule

/*
module fa(input a, b, cin, output sum, cout);
    assign sum  = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule
*/

module add #(parameter W = 4) (
    input [W-1:0] a, b,
    output reg [W-1:0] sum
);
    always_comb sum = a + b;
endmodule

module inc #(parameter W = 4) (
    input [W-1:0] a,
    output reg [W-1:0] b
);
    always_comb b = a + 1;
endmodule

module cmp #(parameter W = 4) (
    input [W-1:0] a, b,
    output reg lt
);
    always_comb lt = (a < b);
endmodule

module bshift #(parameter WIDTH = 4) (
    input              clk, rst,
    input  [WIDTH-1:0] in,
    output reg [WIDTH-1:0] out
);
    always_ff @(posedge clk) begin
        if (rst) out <= 0;
        else     out <= in >> 1;
    end
endmodule
